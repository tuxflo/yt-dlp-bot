from pathlib import Path

from yt_shared.constants import KIKA_HOSTS
from yt_shared.enums import DownMediaType

from ytdl_opts.per_host._base import AbstractHostConfig, BaseHostConfModel
from ytdl_opts.per_host._registry import HostConfRegistry


class KikaHostModel(BaseHostConfModel):
    pass


class KikaHost(AbstractHostConfig, metaclass=HostConfRegistry):
    ALLOW_NULL_HOSTNAMES = False
    HOSTNAMES = KIKA_HOSTS
    ENCODE_AUDIO = False
    ENCODE_VIDEO = False

    PLAYLIST_URL_HINT = (
        'For kika.de use the show page, for example\n'
        'https://www.kika.de/mako-einfach-meerjungfrau/mako-einfach-meerjungfrau-100\n'
        'instead of the episode listing\n'
        'https://www.kika.de/mako-einfach-meerjungfrau/videos/alle-folgen-302'
    )

    def build_config(
        self, media_type: DownMediaType, curr_tmp_dir: Path
    ) -> KikaHostModel:
        return KikaHostModel(
            hostnames=self.HOSTNAMES,
            encode_audio=self.ENCODE_AUDIO,
            encode_video=self.ENCODE_VIDEO,
            ffmpeg_audio_opts=self.FFMPEG_AUDIO_OPTS,
            ffmpeg_video_opts=self.FFMPEG_VIDEO_OPTS,
            ytdl_opts=self._build_ytdl_opts(media_type, curr_tmp_dir),
        )

    def _build_custom_ytdl_video_opts(self) -> tuple[str, ...]:
        # KiKA serves every resolution both as HLS and as a plain MP4. Prefer the
        # plain file: it is a single request instead of several hundred fragments,
        # at the same resolution, which makes a long series far less likely to fail.
        return '--format-sort', 'res,proto:https,vcodec:h265,h264'
