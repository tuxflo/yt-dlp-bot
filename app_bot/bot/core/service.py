import logging
import re
from datetime import UTC, datetime, timedelta
from itertools import product
from urllib.parse import urljoin, urlparse

from pyrogram.types import Message
from yt_shared.constants import DEFAULT_STALE_TASK_HOURS, REMOVE_QUERY_PARAMS_HOSTS
from yt_shared.db.session import get_db
from yt_shared.enums import TaskSource, TelegramChatType, VideoQuality
from yt_shared.rabbit.publisher import RmqPublisher
from yt_shared.repositories.task import TaskRepository
from yt_shared.schemas.media import InbMediaPayload
from yt_shared.schemas.url import URL

from bot.core.schemas import UserSchema
from bot.core.utils import can_remove_url_params


class UrlService:
    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._rmq_publisher = RmqPublisher()

    async def process_urls(self, urls: list[URL]) -> None:
        for url in urls:
            await self._send_to_worker(url)

    async def _send_to_worker(self, url: URL) -> bool:
        payload = InbMediaPayload(
            url=url.url,
            original_url=url.original_url,
            message_id=url.message_id,
            ack_message_id=url.ack_message_id,
            from_user_id=url.from_user_id,
            from_chat_id=url.from_chat_id,
            from_chat_type=url.from_chat_type,
            source=TaskSource.BOT,
            save_to_storage=url.save_to_storage,
            download_media_type=url.download_media_type,
            custom_filename=None,
            automatic_extension=False,
            video_quality=url.video_quality,
            playlist=url.playlist,
        )
        is_sent = await self._rmq_publisher.send_for_download(payload)
        if not is_sent:
            self._log.error('Failed to publish URL %s to message broker', url.url)
        return is_sent


class TaskHistoryService:
    """Query and prune the stored download task history."""

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    async def forget_history(self, url_part: str) -> tuple[int, int]:
        """Delete task history matching `url_part`, keeping anything still running.

        Returns the number of deleted and of kept tasks. Downloaded files are not
        touched; only the bot's memory of having downloaded them is.
        """
        # 'Task.updated' is naive UTC, so compare against a naive UTC point in time.
        active_since = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            hours=DEFAULT_STALE_TASK_HOURS
        )
        async for session in get_db():
            repository = TaskRepository(db=session)
            kept = await repository.count_running_tasks_by_url(
                url_part=url_part, active_since=active_since
            )
            deleted = await repository.delete_tasks_by_url(
                url_part=url_part, active_since=active_since
            )
        return deleted, kept


class UrlParser:
    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    @staticmethod
    def _preprocess_urls(urls: list[str]) -> dict[str, str]:
        preprocessed_urls: dict[str, str] = {}
        for url in urls:
            if can_remove_url_params(url=url, matching_hosts=REMOVE_QUERY_PARAMS_HOSTS):
                preprocessed_urls[url] = urljoin(url, urlparse(url).path)
            else:
                preprocessed_urls[url] = url
        return preprocessed_urls

    @staticmethod
    def pop_video_quality(words: list[str]) -> tuple[VideoQuality, list[str]]:
        """Split a leading quality keyword off the command arguments.

        Returns the requested quality and the remaining words, so
        '/series MEDIUM <url>' caps the resolution while '/series <url>' does not.
        """
        if words and words[0].upper() in VideoQuality.choices():
            return VideoQuality(words[0].upper()), words[1:]
        return VideoQuality.BEST, words

    @classmethod
    def pop_video_quality_from_text(cls, text: str) -> tuple[VideoQuality, list[str]]:
        """Split a leading quality keyword off a pasted message, return it and the URLs.

        One URL per line as before, but the very first word of the message may be a
        quality keyword, which then applies to every URL in that message. Both
        'MEDIUM <url>' and 'MEDIUM' on its own first line work. Only that first word is
        considered, so a line is never otherwise split and a message that merely
        mentions a URL behaves exactly as it did before.
        """
        lines = text.splitlines()
        if not lines:
            return VideoQuality.BEST, lines

        head = lines[0].split(maxsplit=1)
        # Explicitly check for the keyword rather than comparing the returned quality:
        # a spelled-out 'BEST <url>' must still have its keyword stripped.
        if not head or head[0].upper() not in VideoQuality.choices():
            return VideoQuality.BEST, lines

        quality, remaining = cls.pop_video_quality(head)
        first_line = remaining[0].strip() if remaining else ''
        rest = ([first_line] if first_line else []) + lines[1:]
        return quality, rest

    def parse_urls(
        self,
        urls: list[str],
        context: dict[str, Message | UserSchema],
        playlist: bool = False,
        video_quality: VideoQuality = VideoQuality.BEST,
    ) -> list[URL]:
        message: Message = context['message']
        user: UserSchema = context['user']
        ack_message: Message = context['ack_message']
        from_user_id = message.from_user.id if message.from_user else None
        return [
            URL(
                url=url,
                original_url=orig_url,
                from_chat_id=message.chat.id,
                from_chat_type=TelegramChatType(message.chat.type.value),
                from_user_id=from_user_id,
                message_id=message.id,
                ack_message_id=ack_message.id,
                save_to_storage=user.save_to_storage,
                download_media_type=user.download_media_type,
                video_quality=video_quality,
                playlist=playlist,
            )
            for orig_url, url in self._preprocess_urls(urls).items()
        ]

    def filter_urls(self, urls: list[str], regexes: list[str]) -> list[str]:
        """Return valid urls."""
        self._log.debug('Matching urls: %s against regexes %s', urls, regexes)
        valid_urls: list[str] = []
        for url, regex in product(urls, regexes):
            if re.match(regex, url):
                valid_urls.append(url)

        valid_urls = list(dict.fromkeys(valid_urls))
        self._log.debug('Matched urls: %s', valid_urls)
        return valid_urls
