import html
import logging

from pyrogram.enums import ParseMode
from pyrogram.types import Message
from yt_shared.emoji import SUCCESS_EMOJI
from yt_shared.enums import VideoQuality

from bot.bot.client import VideoBotClient
from bot.core.service import TaskHistoryService, UrlParser, UrlService
from bot.core.utils import bold, code, get_user_id


class TelegramCallback:
    _MSG_SEND_OK: str = (
        f'{SUCCESS_EMOJI} {bold("{count}URL{plural} sent for download")}'
    )
    _MSG_SEND_PLAYLIST_OK: str = (
        f'🔎 {bold("Looking up videos behind {count}series URL{plural}")}'
    )
    _MSG_SEND_FAIL: str = f'🛑 {bold("Failed to send URL for download")}'
    _MSG_SERIES_USAGE: str = (
        f'{bold("Send a series, season or playlist URL:")} /series URL\n'
        f'{bold("Optionally cap the resolution:")} /series MEDIUM URL\n'
        f'LOW 480p · MEDIUM 720p · HIGH 1080p · BEST unlimited (default)'
    )

    _MIN_CLEAR_PATTERN_LEN: int = 3
    _MSG_CLEAR_USAGE: str = (
        f'{bold("Forget the download history for a host:")} /clear youtube\n'
        f'Also works with e.g. {code("arte.tv")} or {code("kika")}. '
        f'Matched against the stored URLs, at least '
        f'{_MIN_CLEAR_PATTERN_LEN} characters, one word.'
    )
    _MSG_CLEAR_FORBIDDEN: str = f'🛑 {bold("Only admins can clear the history")}'

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._url_parser = UrlParser()
        self._url_service = UrlService()
        self._task_service = TaskHistoryService()

    @staticmethod
    async def on_start(client: VideoBotClient, message: Message) -> None:  # noqa: ARG004
        await message.reply(
            f'{bold("Send video URL to start processing")}\n'
            f'{bold("Send /series URL to download a whole series, season or playlist")}\n'
            f'{bold("Cap the resolution with a leading quality:")} MEDIUM URL\n'
            f'{bold("Works for a series too:")} /series MEDIUM URL\n'
            f'LOW 480p · MEDIUM 720p · HIGH 1080p · BEST unlimited (default)\n'
            f'{bold("Forget a host, to download it again:")} /clear youtube',
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.id,
        )

    async def on_message(self, client: VideoBotClient, message: Message) -> None:
        """Receive video URL and send to the download worker."""
        self._log.debug('Received Telegram Message: %s', message)
        text = message.text
        if not text:
            self._log.debug('Forwarded message, skipping')
            return

        video_quality, urls = self._url_parser.pop_video_quality_from_text(text)
        await self._process_urls(
            client=client,
            message=message,
            urls=urls,
            playlist=False,
            video_quality=video_quality,
        )

    async def on_series(self, client: VideoBotClient, message: Message) -> None:
        """Receive series/season/playlist URL and download all videos behind it."""
        self._log.debug('Received Telegram series command: %s', message)
        words = list(message.command[1:]) if message.command else []
        video_quality, urls = self._url_parser.pop_video_quality(words)
        if not urls:
            await message.reply(
                self._MSG_SERIES_USAGE,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id,
            )
            return

        await self._process_urls(
            client=client,
            message=message,
            urls=urls,
            playlist=True,
            video_quality=video_quality,
        )

    async def on_clear(self, client: VideoBotClient, message: Message) -> None:
        """Forget the download history for a host, so its videos can be fetched again."""
        self._log.debug('Received Telegram clear command: %s', message)
        args = list(message.command[1:]) if message.command else []
        url_part = args[0].strip() if args else ''

        if len(url_part) < self._MIN_CLEAR_PATTERN_LEN or len(args) != 1:
            await message.reply(
                self._MSG_CLEAR_USAGE,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id,
            )
            return

        if get_user_id(message) not in client.admin_users:
            self._log.warning('Non-admin tried to clear history: %s', message.chat.id)
            await message.reply(
                self._MSG_CLEAR_FORBIDDEN,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id,
            )
            return

        deleted, kept = await self._task_service.forget_history(url_part)
        self._log.info(
            'Cleared %d task(s) matching "%s", kept %d running', deleted, url_part, kept
        )
        await message.reply(
            self._format_clear_result(url_part=url_part, deleted=deleted, kept=kept),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.id,
        )

    def _format_clear_result(self, url_part: str, deleted: int, kept: int) -> str:
        safe = html.escape(url_part)
        if not deleted and not kept:
            return f'🧹 {bold("Nothing stored")} for {code(safe)}'

        lines = [f'🧹 {bold(f"Forgot {deleted} task(s)")} matching {code(safe)}']
        if kept:
            lines.append(f'⏳ {bold(f"Kept {kept}")} still running')
        lines.append('💾 Downloaded files were not touched')
        lines.append('↩️ Send the link again to download it anew')
        return '\n'.join(lines)

    async def _process_urls(
        self,
        client: VideoBotClient,
        message: Message,
        urls: list[str],
        playlist: bool,
        video_quality: VideoQuality = VideoQuality.BEST,
    ) -> None:
        if not urls:
            self._log.debug('No urls to download, skipping message')
            return

        user = client.allowed_users[get_user_id(message)]
        if user.use_url_regex_match:
            urls = self._url_parser.filter_urls(
                urls=urls, regexes=client.conf.telegram.url_validation_regexes
            )
            if not urls:
                self._log.debug('No urls to download, skipping message')
                return

        ack_message = await self._send_acknowledge_message(
            message=message,
            url_count=len(urls),
            playlist=playlist,
            video_quality=video_quality,
        )
        context = {'message': message, 'user': user, 'ack_message': ack_message}
        url_objects = self._url_parser.parse_urls(
            urls=urls,
            context=context,
            playlist=playlist,
            video_quality=video_quality,
        )
        await self._url_service.process_urls(url_objects)

    async def _send_acknowledge_message(
        self,
        message: Message,
        url_count: int,
        playlist: bool = False,
        video_quality: VideoQuality = VideoQuality.BEST,
    ) -> Message:
        return await message.reply(
            text=self._format_acknowledge_text(
                url_count=url_count, playlist=playlist, video_quality=video_quality
            ),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.id,
        )

    def _format_acknowledge_text(
        self,
        url_count: int,
        playlist: bool = False,
        video_quality: VideoQuality = VideoQuality.BEST,
    ) -> str:
        is_multiple = url_count > 1
        template = self._MSG_SEND_PLAYLIST_OK if playlist else self._MSG_SEND_OK
        text = template.format(
            count=f'{url_count} ' if is_multiple else '',
            plural='s' if is_multiple else '',
        )
        max_height = video_quality.max_height
        if max_height:
            text = f'{text}\n📐 {bold(f"Max {max_height}p")} ({video_quality.value})'
        return text
