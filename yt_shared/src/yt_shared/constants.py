from asyncio import Lock
from typing import Final

SHARED_ASYNC_LOCK: Final[Lock] = Lock()

# An unfinished task untouched for this long is treated as orphaned rather than as
# still being worked on, which is what a worker restarted mid-download leaves behind.
DEFAULT_STALE_TASK_HOURS: Final[int] = 6

INSTAGRAM_HOSTS: Final[tuple[str, ...]] = ('instagram.com', 'www.instagram.com')
TIKTOK_HOSTS: Final[tuple[str, ...]] = (
    'tiktok.com',
    'vm.tiktok.com',
    'www.tiktok.com',
    'www.vm.tiktok.com',
)
TWITTER_HOSTS: Final[tuple[str, ...]] = (
    'twitter.com',
    'www.twitter.com',
    'x.com',
    'www.x.com',
    't.co',
    'www.t.co',
)
FACEBOOK_HOSTS: Final[tuple[str, ...]] = ('facebook.com', 'www.facebook.com')
KIKA_HOSTS: Final[tuple[str, ...]] = ('kika.de', 'www.kika.de')
YOUTUBE_HOSTS: Final[tuple[str, ...]] = (
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'music.youtube.com',
    'youtu.be',
    'www.youtu.be',
)

REMOVE_QUERY_PARAMS_HOSTS: Final[set[str]] = {
    *TWITTER_HOSTS,
    *INSTAGRAM_HOSTS,
    *FACEBOOK_HOSTS,
}
