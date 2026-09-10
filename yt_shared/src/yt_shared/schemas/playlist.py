from typing import Literal

from pydantic import StrictInt, StrictStr

from yt_shared.enums import RabbitPayloadType
from yt_shared.schemas.base_rabbit import BaseRabbitDownloadPayload


class PlaylistInfoPayload(BaseRabbitDownloadPayload):
    """Payload with expanded playlist/series context sent back to the bot."""

    type: Literal[RabbitPayloadType.PLAYLIST_INFO] = RabbitPayloadType.PLAYLIST_INFO
    url: StrictStr
    title: StrictStr | None
    total_count: StrictInt
    queued_count: StrictInt
    skipped_count: StrictInt = 0
    """Entries skipped because they were already downloaded or are still queued."""
