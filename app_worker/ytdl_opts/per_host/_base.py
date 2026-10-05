import logging
from abc import abstractmethod
from copy import deepcopy
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from yt_shared.enums import DownMediaType

from worker.utils import cli_to_api

try:
    from ytdl_opts.user import (
        AUDIO_FORMAT_YTDL_OPTS,
        AUDIO_YTDL_OPTS,
        DEFAULT_VIDEO_FORMAT_SORT_OPT,
        DEFAULT_YTDL_OPTS,
        FINAL_AUDIO_FORMAT,
        FINAL_THUMBNAIL_FORMAT,
        VIDEO_YTDL_OPTS,
    )
except ImportError:
    from ytdl_opts.default import (
        AUDIO_FORMAT_YTDL_OPTS,
        AUDIO_YTDL_OPTS,
        DEFAULT_VIDEO_FORMAT_SORT_OPT,
        DEFAULT_YTDL_OPTS,
        FINAL_AUDIO_FORMAT,
        FINAL_THUMBNAIL_FORMAT,
        VIDEO_YTDL_OPTS,
    )

# Imported separately so that an existing 'user.py' copied from an older 'default.py'
# (without this option) keeps overriding all the other options.
try:
    from ytdl_opts.user import PLAYLIST_YTDL_OPTS
except ImportError:
    from ytdl_opts.default import PLAYLIST_YTDL_OPTS


class BaseHostConfModel(BaseModel):
    # TODO: Add validators.
    model_config = ConfigDict(
        strict=True, frozen=True, validate_assignment=True, validate_default=True
    )

    hostnames: tuple[str, ...]

    encode_audio: bool
    encode_video: bool

    ffmpeg_audio_opts: str | None
    ffmpeg_video_opts: str | None

    ytdl_opts: dict


class AbstractHostConfig:
    """Abstract yt-dlp host config."""

    ALLOW_NULL_HOSTNAMES: bool | None = None
    HOSTNAMES: tuple[str, ...] | None = None

    # Shown when a '/series' URL of this host cannot be read as a playlist, to point
    # at the link that does work. Hosts where the overview page is easy to confuse
    # with an episode listing should set it.
    PLAYLIST_URL_HINT: str | None = None

    CUSTOM_VIDEO_YTDL_OPTS: list[str] | None = None

    ENCODE_AUDIO: bool | None = None
    ENCODE_VIDEO: bool | None = None

    KEEP_VIDEO_OPTION: str = '--keep-video'
    FORMAT_SORT_OPTION_NAME: str = '--format-sort'

    DEFAULT_YTDL_OPTS: tuple[str, ...] = DEFAULT_YTDL_OPTS
    PLAYLIST_YTDL_OPTS: tuple[str, ...] = PLAYLIST_YTDL_OPTS

    AUDIO_YTDL_OPTS: tuple[str, ...] = AUDIO_YTDL_OPTS
    AUDIO_FORMAT_YTDL_OPTS: tuple[str, ...] = AUDIO_FORMAT_YTDL_OPTS

    FINAL_AUDIO_FORMAT: str = FINAL_AUDIO_FORMAT
    FINAL_THUMBNAIL_FORMAT: str = FINAL_THUMBNAIL_FORMAT

    DEFAULT_VIDEO_YTDL_OPTS: tuple[str, ...] = VIDEO_YTDL_OPTS
    DEFAULT_VIDEO_FORMAT_SORT_OPT: tuple[str, ...] = DEFAULT_VIDEO_FORMAT_SORT_OPT

    FFMPEG_AUDIO_OPTS: str | None = None
    FFMPEG_VIDEO_OPTS: str | None = None

    def __init__(self, url: str, max_height: int | None = None) -> None:
        self._log = logging.getLogger(self.__class__.__name__)
        self._validate_hostname()
        self.url = url
        self._max_height = max_height
        self._log.info(
            'Instantiating "%s" for url "%s", max height %s',
            self.__class__.__name__,
            url,
            max_height or 'unlimited',
        )

    def _validate_hostname(self) -> None:
        if not self.ALLOW_NULL_HOSTNAMES and not self.HOSTNAMES:
            raise ValueError('Hostname(s) must be set before instantiation.')

    @abstractmethod
    def build_config(
        self, media_type: DownMediaType, curr_tmp_dir: str
    ) -> BaseHostConfModel:
        pass

    def _build_ytdl_opts(self, media_type: DownMediaType, curr_tmp_dir: Path) -> dict:
        def _add_video_opts(ytdl_opts_: list[str]) -> None:
            ytdl_opts_.extend(self.DEFAULT_VIDEO_YTDL_OPTS)
            ytdl_opts_.extend(
                self._apply_max_height(self._build_custom_ytdl_video_opts())
            )

        ytdl_opts = list(deepcopy(self.DEFAULT_YTDL_OPTS))

        match media_type:
            case DownMediaType.AUDIO:
                ytdl_opts.extend(self.AUDIO_YTDL_OPTS)
                ytdl_opts.extend(self.AUDIO_FORMAT_YTDL_OPTS)
            case DownMediaType.VIDEO:
                _add_video_opts(ytdl_opts)
            case DownMediaType.AUDIO_VIDEO:
                ytdl_opts.extend(self.AUDIO_YTDL_OPTS)
                _add_video_opts(ytdl_opts)
                ytdl_opts.append(self.KEEP_VIDEO_OPTION)

        ytdl_opts = cli_to_api(ytdl_opts)
        ytdl_opts['outtmpl']['default'] = str(
            curr_tmp_dir / ytdl_opts['outtmpl']['default']
        )
        return ytdl_opts

    def build_playlist_ytdl_opts(self) -> dict:
        """Build options used to list playlist/series entries without downloading."""
        return cli_to_api(list(deepcopy(self.PLAYLIST_YTDL_OPTS)))

    def _apply_max_height(self, sort_opts: tuple[str, ...]) -> tuple[str, ...]:
        """Pin the resolution preference of a '--format-sort' option to a maximum.

        'res' alone means "prefer the highest resolution", which is how a 4K stream
        gets picked. Giving it a value makes 'yt-dlp' prefer that resolution instead.
        """
        if not self._max_height:
            return sort_opts

        opts = list(sort_opts)
        for idx, opt in enumerate(opts):
            if opt != self.FORMAT_SORT_OPTION_NAME or idx + 1 >= len(opts):
                continue
            fields = [field.strip() for field in opts[idx + 1].split(',')]
            capped = f'res:{self._max_height}'
            fields = [capped if field == 'res' else field for field in fields]
            if capped not in fields:
                fields.insert(0, capped)
            opts[idx + 1] = ','.join(fields)
        return tuple(opts)

    def normalize_playlist_url(self) -> str:
        """Rewrite the URL into the form that lists a playlist most reliably.

        Hosts that expose the same playlist under several URL shapes should override
        this to return the one 'yt-dlp' handles best.
        """
        return self.url

    @abstractmethod
    def _build_custom_ytdl_video_opts(self) -> tuple[str, ...]:
        pass
