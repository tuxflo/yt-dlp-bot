import re
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from yt_shared.constants import YOUTUBE_HOSTS
from yt_shared.enums import DownMediaType

from ytdl_opts.per_host._base import AbstractHostConfig, BaseHostConfModel
from ytdl_opts.per_host._registry import HostConfRegistry

# A legacy '/show/VL<playlist_id>' URL addresses the very same playlist as
# '/playlist?list=<playlist_id>'.
_SHOW_URL_RE: Final[re.Pattern[str]] = re.compile(
    r'^/show/VL(?P<playlist_id>[\w-]+)/?$'
)
_PLAYLIST_URL_TPL: Final[str] = 'https://www.youtube.com/playlist?list={playlist_id}'


class YouTubeHostModel(BaseHostConfModel):
    pass


class YouTubeHost(AbstractHostConfig, metaclass=HostConfRegistry):
    ALLOW_NULL_HOSTNAMES = False
    HOSTNAMES = YOUTUBE_HOSTS
    ENCODE_AUDIO = False
    ENCODE_VIDEO = False

    def build_config(
        self, media_type: DownMediaType, curr_tmp_dir: Path
    ) -> YouTubeHostModel:
        return YouTubeHostModel(
            hostnames=self.HOSTNAMES,
            encode_audio=self.ENCODE_AUDIO,
            encode_video=self.ENCODE_VIDEO,
            ffmpeg_audio_opts=self.FFMPEG_AUDIO_OPTS,
            ffmpeg_video_opts=self.FFMPEG_VIDEO_OPTS,
            ytdl_opts=self._build_ytdl_opts(media_type, curr_tmp_dir),
        )

    def normalize_playlist_url(self) -> str:
        """Rewrite a legacy '/show/VL<id>' playlist URL to '/playlist?list=<id>'.

        The '/show/' form only lists its videos when YouTube's own tracking query
        parameters happen to be present, titles the playlist "show" instead of its real
        name, and makes 'yt-dlp' retry on incomplete responses. The canonical playlist
        URL has none of those problems.
        """
        match = _SHOW_URL_RE.match(urlsplit(self.url).path)
        if not match:
            return self.url

        normalized = _PLAYLIST_URL_TPL.format(playlist_id=match.group('playlist_id'))
        self._log.info('Normalized playlist URL "%s" to "%s"', self.url, normalized)
        return normalized

    def _build_custom_ytdl_video_opts(self) -> tuple[str, ...]:
        return self.DEFAULT_VIDEO_FORMAT_SORT_OPT
