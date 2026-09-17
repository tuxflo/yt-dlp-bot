from pydantic import DirectoryPath, PositiveInt, field_validator
from yt_shared.config import CommonSettings


class WorkerSettings(CommonSettings):
    APPLICATION_NAME: str
    MAX_SIMULTANEOUS_DOWNLOADS: int
    MAX_PLAYLIST_ITEMS: PositiveInt = 100
    # An unfinished task untouched for this long is treated as orphaned, which happens
    # when the worker is restarted mid-download. Keep it comfortably above the time
    # your slowest download takes.
    STALE_TASK_HOURS: PositiveInt = 6
    STORAGE_PATH: DirectoryPath
    THUMBNAIL_FRAME_SECOND: float
    INSTAGRAM_ENCODE_TO_H264: bool
    FACEBOOK_ENCODE_TO_H264: bool
    MAX_DOWNLOAD_THREADS: str

    @field_validator('MAX_DOWNLOAD_THREADS')
    @classmethod
    def validate_max_download_threads(cls, value: str) -> str:
        """Value must be integer enclosed as string."""
        if not value.isdigit():
            raise ValueError('Value must be integer enclosed as string.')
        return value


settings = WorkerSettings()
