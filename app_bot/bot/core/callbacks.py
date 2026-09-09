import logging

from pyrogram.enums import ParseMode
from pyrogram.types import Message
from yt_shared.emoji import SUCCESS_EMOJI

from bot.bot.client import VideoBotClient
from bot.core.service import UrlParser, UrlService
from bot.core.utils import bold, get_user_id


class TelegramCallback:
    _MSG_SEND_OK: str = (
        f'{SUCCESS_EMOJI} {bold("{count}URL{plural} sent for download")}'
    )
    _MSG_SEND_PLAYLIST_OK: str = (
        f'🔎 {bold("Looking up videos behind {count}series URL{plural}")}'
    )
    _MSG_SEND_FAIL: str = f'🛑 {bold("Failed to send URL for download")}'
    _MSG_SERIES_USAGE: str = bold('Send a series, season or playlist URL: /series URL')

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._url_parser = UrlParser()
        self._url_service = UrlService()

    @staticmethod
    async def on_start(client: VideoBotClient, message: Message) -> None:  # noqa: ARG004
        await message.reply(
            f'{bold("Send video URL to start processing")}\n'
            f'{bold("Send /series URL to download a whole series, season or playlist")}',
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

        await self._process_urls(
            client=client, message=message, urls=text.splitlines(), playlist=False
        )

    async def on_series(self, client: VideoBotClient, message: Message) -> None:
        """Receive series/season/playlist URL and download all videos behind it."""
        self._log.debug('Received Telegram series command: %s', message)
        urls = list(message.command[1:]) if message.command else []
        if not urls:
            await message.reply(
                self._MSG_SERIES_USAGE,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=message.id,
            )
            return

        await self._process_urls(
            client=client, message=message, urls=urls, playlist=True
        )

    async def _process_urls(
        self,
        client: VideoBotClient,
        message: Message,
        urls: list[str],
        playlist: bool,
    ) -> None:
        user = client.allowed_users[get_user_id(message)]
        if user.use_url_regex_match:
            urls = self._url_parser.filter_urls(
                urls=urls, regexes=client.conf.telegram.url_validation_regexes
            )
            if not urls:
                self._log.debug('No urls to download, skipping message')
                return

        ack_message = await self._send_acknowledge_message(
            message=message, url_count=len(urls), playlist=playlist
        )
        context = {'message': message, 'user': user, 'ack_message': ack_message}
        url_objects = self._url_parser.parse_urls(
            urls=urls, context=context, playlist=playlist
        )
        await self._url_service.process_urls(url_objects)

    async def _send_acknowledge_message(
        self, message: Message, url_count: int, playlist: bool = False
    ) -> Message:
        return await message.reply(
            text=self._format_acknowledge_text(url_count=url_count, playlist=playlist),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.id,
        )

    def _format_acknowledge_text(self, url_count: int, playlist: bool = False) -> str:
        is_multiple = url_count > 1
        template = self._MSG_SEND_PLAYLIST_OK if playlist else self._MSG_SEND_OK
        return template.format(
            count=f'{url_count} ' if is_multiple else '',
            plural='s' if is_multiple else '',
        )
