from enum import StrEnum, unique
from typing import Final


@unique
class StrChoiceEnum(StrEnum):
    @classmethod
    def choices(cls) -> tuple[str, ...]:
        return tuple(x.value for x in cls)


class TaskStatus(StrChoiceEnum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    FAILED = 'FAILED'
    DONE = 'DONE'


class TaskSource(StrChoiceEnum):
    API = 'API'
    BOT = 'BOT'


class RabbitPayloadType(StrChoiceEnum):
    DOWNLOAD_ERROR = 'DOWNLOAD_ERROR'
    GENERAL_ERROR = 'GENERAL_ERROR'
    SUCCESS = 'SUCCESS'
    PLAYLIST_INFO = 'PLAYLIST_INFO'


class TelegramChatType(StrChoiceEnum):
    PRIVATE = 'private'
    BOT = 'bot'
    GROUP = 'group'
    SUPERGROUP = 'supergroup'
    CHANNEL = 'channel'


class DownMediaType(StrChoiceEnum):
    """Media can be audio, video or both.

    1. Only download/extract audio
    2. Video with muxed audio
    3. Both 1) and 2)
    """

    AUDIO = 'AUDIO'
    VIDEO = 'VIDEO'
    AUDIO_VIDEO = 'AUDIO_VIDEO'


class VideoQuality(StrChoiceEnum):
    """Upper bound on the downloaded video resolution.

    Capping the resolution keeps files playable on weaker hardware and cuts the CPU
    cost of downloading, since sites happily serve 4K when nothing limits them.
    """

    LOW = 'LOW'
    MEDIUM = 'MEDIUM'
    HIGH = 'HIGH'
    BEST = 'BEST'

    @property
    def max_height(self) -> int | None:
        """Maximum video height in pixels, or None for no limit."""
        return _QUALITY_TO_MAX_HEIGHT[self]


_QUALITY_TO_MAX_HEIGHT: Final[dict[VideoQuality, int | None]] = {
    VideoQuality.LOW: 480,
    VideoQuality.MEDIUM: 720,
    VideoQuality.HIGH: 1080,
    VideoQuality.BEST: None,
}


class MediaFileType(StrChoiceEnum):
    AUDIO = 'AUDIO'
    VIDEO = 'VIDEO'


class YtdlpReleaseChannelType(StrChoiceEnum):
    STABLE = 'STABLE'
    NIGHTLY = 'NIGHTLY'
    MASTER = 'MASTER'
