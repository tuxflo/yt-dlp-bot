import asyncio
import logging
import traceback

from yt_dlp import version as ytdlp_version
from yt_shared.db.session import get_db
from yt_shared.models import Task
from yt_shared.rabbit.publisher import RmqPublisher
from yt_shared.repositories.task import TaskRepository
from yt_shared.schemas.error import ErrorDownloadGeneralPayload, ErrorDownloadPayload
from yt_shared.schemas.media import DownMedia, InbMediaPayload
from yt_shared.schemas.playlist import PlaylistInfoPayload
from yt_shared.schemas.success import SuccessDownloadPayload

from worker.core.config import settings
from worker.core.downloader import MediaDownloader
from worker.core.exceptions import DownloadVideoServiceError, GeneralVideoServiceError
from worker.core.media_service import MediaService
from worker.core.playlist import Playlist, PlaylistExtractor
from ytdl_opts.per_host._registry import get_host_conf


class InboundPayloadHandler:
    def __init__(self) -> None:
        """Initialize the InboundPayloadHandler with a logger and RMQ publisher."""
        self._log = logging.getLogger(self.__class__.__name__)
        self._rmq_publisher = RmqPublisher()
        self._playlist_extractor = PlaylistExtractor()

    async def handle(self, media_payload: InbMediaPayload) -> None:
        """Handle the inbound media payload.

        Args:
            media_payload (InbMediaPayload): The inbound media payload to handle.

        """
        try:
            await self._handle(media_payload)
        except Exception as err:
            await self._send_general_error(err, media_payload)

    async def _handle(self, media_payload: InbMediaPayload) -> None:
        """Process the media payload and handle any errors.

        Args:
            media_payload (InbMediaPayload): The inbound media payload to process.

        """
        if media_payload.playlist:
            await self._handle_playlist(media_payload)
            return

        async for session in get_db():
            media_service = MediaService(
                media_payload=media_payload,
                downloader=MediaDownloader(),
                task_repository=TaskRepository(db=session),
            )
            try:
                media, task = await media_service.process()
            except DownloadVideoServiceError as err:
                await self._send_failed_video_download_task(err, media_payload)
                return

            if not media or not task:
                err_msg = (
                    f'Media or task is None, cannot proceed: '
                    f'media - {media}, task - {task}'
                )
                self._log.error(err_msg)
                raise RuntimeError(err_msg)
            await self._send_finished_task(task, media, media_payload)

    async def _handle_playlist(self, media_payload: InbMediaPayload) -> None:
        """Expand a playlist/series URL and queue each entry as its own download.

        Args:
            media_payload (InbMediaPayload): The inbound media payload to expand.

        """
        host_conf = get_host_conf(media_payload.url)
        playlist: Playlist = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._playlist_extractor.extract(
                host_conf=host_conf, max_items=settings.MAX_PLAYLIST_ITEMS
            ),
        )

        queued_count = 0
        for entry in playlist.entries:
            entry_payload = media_payload.model_copy(
                update={
                    'id': None,
                    'url': entry.url,
                    'original_url': entry.url,
                    'playlist': False,
                    # The acknowledgment message is replaced by the playlist info one.
                    'ack_message_id': None,
                    # A single custom name cannot be applied to many videos.
                    'custom_filename': None,
                }
            )
            if await self._rmq_publisher.send_for_download(entry_payload):
                queued_count += 1
            else:
                self._log.error(
                    'Failed to publish playlist entry %s to message broker', entry.url
                )

        await self._send_playlist_info(
            playlist=playlist, media_payload=media_payload, queued_count=queued_count
        )

    async def _send_playlist_info(
        self, playlist: Playlist, media_payload: InbMediaPayload, queued_count: int
    ) -> None:
        """Send expanded playlist context back to the bot.

        Args:
            playlist (Playlist): The expanded playlist.
            media_payload (InbMediaPayload): The inbound media payload.
            queued_count (int): Number of entries actually sent for download.

        """
        info_payload = PlaylistInfoPayload(
            message_id=media_payload.message_id,
            from_chat_id=media_payload.from_chat_id,
            from_chat_type=media_payload.from_chat_type,
            from_user_id=media_payload.from_user_id,
            context=media_payload,
            url=playlist.url,
            title=playlist.title,
            total_count=playlist.total_count,
            queued_count=queued_count,
        )
        await self._rmq_publisher.send_playlist_info(info_payload)

    async def _send_finished_task(
        self, task: Task, media: DownMedia, media_payload: InbMediaPayload
    ) -> None:
        """Send a finished task message.

        Args:
            task (Task): The task that was completed.
            media (DownMedia): The downloaded media.
            media_payload (InbMediaPayload): The inbound media payload.

        """
        success_payload = SuccessDownloadPayload(
            task_id=task.id,
            media=media,
            message_id=task.message_id,
            from_chat_id=media_payload.from_chat_id,
            from_chat_type=media_payload.from_chat_type,
            from_user_id=task.from_user_id,
            context=media_payload,
            yt_dlp_version=ytdlp_version.__version__,
        )
        await self._rmq_publisher.send_download_finished(success_payload)

    async def _send_failed_video_download_task(
        self, err: DownloadVideoServiceError, media_payload: InbMediaPayload
    ) -> None:
        """Send a failed video download task message.

        Args:
            err (DownloadVideoServiceError): The error that occurred during download.
            media_payload (InbMediaPayload): The inbound media payload.

        """
        task = err.task
        err_payload = ErrorDownloadPayload(
            task_id=task.id,
            message_id=task.message_id,
            from_chat_id=media_payload.from_chat_id,
            from_chat_type=media_payload.from_chat_type,
            from_user_id=media_payload.from_user_id,
            message='Download error',
            url=media_payload.url,
            context=media_payload,
            yt_dlp_version=ytdlp_version.__version__,
            exception_msg=str(err),
            exception_type=err.__class__.__name__,
        )
        await self._rmq_publisher.send_download_error(err_payload)

    async def _send_general_error(
        self, err: GeneralVideoServiceError | Exception, media_payload: InbMediaPayload
    ) -> None:
        """Send a general error message.

        Args:
            err (GeneralVideoServiceError | Exception): The error that occurred.
            media_payload (InbMediaPayload): The inbound media payload.

        """
        task: Task | None = getattr(err, 'task', None)
        err_payload = ErrorDownloadGeneralPayload(
            task_id=task.id if task else 'N/A',
            message_id=media_payload.message_id,
            from_chat_id=media_payload.from_chat_id,
            from_chat_type=media_payload.from_chat_type,
            from_user_id=media_payload.from_user_id,
            message='General worker error',
            url=media_payload.url,
            context=media_payload,
            yt_dlp_version=ytdlp_version.__version__,
            exception_msg=traceback.format_exc(),
            exception_type=err.__class__.__name__,
        )
        await self._rmq_publisher.send_download_error(err_payload)
