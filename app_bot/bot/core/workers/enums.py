from enum import StrEnum


class RabbitWorkerType(StrEnum):
    ERROR = 'ERROR'
    SUCCESS = 'SUCCESS'
    PLAYLIST_INFO = 'PLAYLIST_INFO'
