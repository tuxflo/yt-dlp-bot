from typing import Final

from yt_shared.models import Task

# Failures that retrying can never fix: the URL is not supported, or the media is gone,
# private or unavailable where the worker runs. Matched against the 'yt-dlp' error
# message, so keep these to phrases that are unambiguously permanent — anything not
# listed here is treated as transient and retried, which is the safer default.
_PERMANENT_ERROR_PHRASES: Final[frozenset[str]] = frozenset(
    {
        'unsupported url',
        'is not a valid url',
        'incomplete youtube id',
        'video unavailable',
        'this video is unavailable',
        'private video',
        'sign in if you',
        'members-only content',
        'removed by the uploader',
        'has been terminated',
        # Covers both "not available in your country" and yt-dlp's longer
        # "the uploader has not made this video available in your country".
        'available in your country',
        'not available from your location',
        'who has blocked it in your country',
        'video does not exist',
        'no longer available',
    }
)


def is_permanent_download_error(message: str) -> bool:
    """Whether a download failure is pointless to retry."""
    lowered = message.lower()
    return any(phrase in lowered for phrase in _PERMANENT_ERROR_PHRASES)


class BaseVideoServiceError(Exception):
    def __init__(self, message: str, task: Task | None = None) -> None:
        super().__init__(message)
        self.task = task


class GeneralVideoServiceError(BaseVideoServiceError):
    pass


class DownloadVideoServiceError(BaseVideoServiceError):
    pass


class MediaDownloaderError(Exception):
    pass


class PlaylistExtractorError(Exception):
    pass
