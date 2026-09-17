import asyncio
import logging
import traceback
from datetime import UTC, datetime, timedelta
from typing import Final

from yt_dlp import version as ytdlp_version
from yt_shared.db.session import get_db
from yt_shared.models import Task
from yt_shared.rabbit.publisher import RmqPublisher
from yt_shared.repositories.task import TaskRepository
from yt_shared.schemas.error import ErrorDownloadGeneralPayload, ErrorDownloadPayload
from yt_shared.schemas.media import DownMedia, InbMediaPayload
from yt_shared.schemas.playlist import PlaylistInfoPayload
from yt_shared.schemas.success import SuccessDownloadPayload
from yt_shared.utils.tasks.tasks import create_task

from worker.core.config import settings
from worker.core.downloader import MediaDownloader
from worker.core.exceptions import DownloadVideoServiceError, GeneralVideoServiceError
from worker.core.media_service import MediaService
from worker.core.playlist import Playlist, PlaylistEntry, PlaylistExtractor
from ytdl_opts.per_host._registry import get_host_conf

_MS_IN_SECOND: Final[int] = 1000


class InboundPayloadHandler:
    def __init__(self) -> None:
        """Initialize the InboundPayloadHandler with a logger and RMQ publisher."""
        self._log = logging.getLogger(self.__class__.__name__)
        self._rmq_publisher = RmqPublisher()
        self._playlist_extractor = PlaylistExtractor()
        # The RabbitMQ prefetch count cannot bound the downloads: a message is
        # acknowledged before its download starts, so the broker keeps delivering and
        # every delivery is handled in its own task. Without this semaphore a 68
        # episode series starts as many downloads at once as the default asyncio
        # executor has threads, which is min(32, cpu_count + 4) and unrelated to
        # anything configured.
        self._download_semaphore = asyncio.Semaphore(
            settings.MAX_SIMULTANEOUS_DOWNLOADS
        )

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
                async with self._download_semaphore:
                    media, task = await media_service.process()
            except DownloadVideoServiceError as err:
                await self._handle_download_failure(err, media_payload)
                return

            if not media or not task:
                err_msg = (
                    f'Media or task is None, cannot proceed: '
                    f'media - {media}, task - {task}'
                )
                self._log.error(err_msg)
                raise RuntimeError(err_msg)
            await self._send_finished_task(task, media, media_payload)

    async def _handle_download_failure(
        self, err: DownloadVideoServiceError, media_payload: InbMediaPayload
    ) -> None:
        """Re-queue the failed download or report it if no attempts are left.

        Args:
            err (DownloadVideoServiceError): The error that occurred during download.
            media_payload (InbMediaPayload): The inbound media payload that failed.

        """
        if media_payload.retry_count >= settings.CONSUMER_NUMBER_OF_RETRY:
            self._log.error(
                'Giving up on %s after %d attempts',
                media_payload.url,
                media_payload.retry_count + 1,
            )
            await self._send_failed_video_download_task(err, media_payload)
            return

        delay = settings.RESEND_DELAY_MS / _MS_IN_SECOND
        self._log.warning(
            'Download of %s failed, retrying in %.0fs (attempt %d of %d)',
            media_payload.url,
            delay,
            media_payload.retry_count + 2,
            settings.CONSUMER_NUMBER_OF_RETRY + 1,
        )
        task_name = f'Retry download of {media_payload.url}'
        create_task(
            self._resend_for_download(media_payload=media_payload, delay=delay),
            task_name=task_name,
            logger=self._log,
            exception_message='Task "%s" raised an exception',
            exception_message_args=(task_name,),
        )

    async def _resend_for_download(
        self, media_payload: InbMediaPayload, delay: float
    ) -> None:
        """Publish the payload again after a delay, marked as one more attempt.

        Args:
            media_payload (InbMediaPayload): The inbound media payload to re-publish.
            delay (float): Seconds to wait before re-publishing.

        """
        await asyncio.sleep(delay)
        retry_payload = media_payload.model_copy(
            update={
                # The previous task is already marked as failed, so a retry needs its
                # own task instead of reusing the existing, non-pending one.
                'id': None,
                'retry_count': media_payload.retry_count + 1,
            }
        )
        if not await self._rmq_publisher.send_for_download(retry_payload):
            self._log.error(
                'Failed to publish retry of %s to message broker', media_payload.url
            )

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

        entries = await self._filter_already_handled(playlist.entries)
        skipped_count = len(playlist.entries) - len(entries)

        queued_count = 0
        for entry in entries:
            entry_payload = media_payload.model_copy(
                update={
                    'id': None,
                    'url': entry.url,
                    'original_url': entry.url,
                    'playlist': False,
                    # Groups the episodes into their own storage subdirectory.
                    'playlist_title': playlist.title,
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
            playlist=playlist,
            media_payload=media_payload,
            queued_count=queued_count,
            skipped_count=skipped_count,
        )

    async def _filter_already_handled(
        self, entries: list[PlaylistEntry]
    ) -> list[PlaylistEntry]:
        """Drop entries that were downloaded before or are still being worked on.

        Re-sending a series link therefore downloads only what is actually missing.
        Previously failed entries are kept so that they are retried, as are entries
        left unfinished by a worker restart.

        Args:
            entries (list[PlaylistEntry]): All entries found behind the playlist URL.

        """
        # 'Task.updated' is naive UTC, so compare against a naive UTC point in time.
        stale_before = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            hours=settings.STALE_TASK_HOURS
        )
        async for session in get_db():
            handled_urls = await TaskRepository(db=session).get_urls_to_skip(
                urls=[entry.url for entry in entries], stale_before=stale_before
            )

        if not handled_urls:
            return entries

        self._log.info(
            'Skipping %d of %d playlist entries, already downloaded or queued',
            len(handled_urls),
            len(entries),
        )
        return [entry for entry in entries if entry.url not in handled_urls]

    async def _send_playlist_info(
        self,
        playlist: Playlist,
        media_payload: InbMediaPayload,
        queued_count: int,
        skipped_count: int,
    ) -> None:
        """Send expanded playlist context back to the bot.

        Args:
            playlist (Playlist): The expanded playlist.
            media_payload (InbMediaPayload): The inbound media payload.
            queued_count (int): Number of entries actually sent for download.
            skipped_count (int): Number of entries skipped as already handled.

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
            skipped_count=skipped_count,
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
        attempts = media_payload.retry_count + 1
        message = 'Download error'
        if attempts > 1:
            message = f'{message} after {attempts} attempts'
        err_payload = ErrorDownloadPayload(
            task_id=task.id,
            message_id=task.message_id,
            from_chat_id=media_payload.from_chat_id,
            from_chat_type=media_payload.from_chat_type,
            from_user_id=media_payload.from_user_id,
            message=message,
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
