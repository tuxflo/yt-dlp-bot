from yt_shared.rabbit.rabbit_config import INFO_QUEUE
from yt_shared.schemas.playlist import PlaylistInfoPayload

from bot.core.handlers.playlist import PlaylistInfoHandler
from bot.core.workers.abstract import AbstractDownloadResultWorker, RabbitWorkerType


class PlaylistInfoResultWorker(AbstractDownloadResultWorker):
    TYPE = RabbitWorkerType.PLAYLIST_INFO
    QUEUE_TYPE = INFO_QUEUE
    SCHEMA_CLS = (PlaylistInfoPayload,)
    HANDLER_CLS = PlaylistInfoHandler

    async def _process_body(self, body: PlaylistInfoPayload) -> None:
        await self.HANDLER_CLS(body=body, bot=self._bot).handle()
