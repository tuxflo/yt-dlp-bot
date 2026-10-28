import re
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from yt_shared.constants import ARD_HOSTS
from yt_shared.enums import DownMediaType

from ytdl_opts.per_host._base import AbstractHostConfig, BaseHostConfModel
from ytdl_opts.per_host._http import fetch_json
from ytdl_opts.per_host._registry import HostConfRegistry

_API_ROOT: Final[str] = 'https://api.ardmediathek.de/page-gateway'
_ITEM_API_TPL: Final[str] = f'{_API_ROOT}/pages/ard/item/{{asset_id}}'
_ASSET_API_TPL: Final[str] = f'{_API_ROOT}/widgets/ard/asset/{{asset_id}}'
_VIDEO_PAGE_TPL: Final[str] = 'https://www.ardmediathek.de/video/{slug}/{asset_id}'

# Path prefixes 'yt-dlp' has an extractor for. Anything else, such as the '/film/'
# and '/dokumentation/' pages the site itself links to, falls through to the generic
# extractor, which scrapes the HTML and finds no video.
_SUPPORTED_PREFIXES: Final[frozenset[str]] = frozenset({'video', 'player', 'live'})
# Handled by 'ARDMediathekCollectionIE', so they belong to '/series', not here.
_PLAYLIST_PREFIXES: Final[frozenset[str]] = frozenset({'sendung', 'serie', 'sammlung'})
# The trailing path segment is a base64url-encoded 'crid://' asset id.
_ASSET_ID_RE: Final[re.Pattern[str]] = re.compile(r'^[A-Za-z0-9_-]{16,}$')

_MAX_LISTED_ITEMS: Final[int] = 6


class ArdHostModel(BaseHostConfModel):
    pass


class ArdHost(AbstractHostConfig, metaclass=HostConfRegistry):
    ALLOW_NULL_HOSTNAMES = False
    HOSTNAMES = ARD_HOSTS
    ENCODE_AUDIO = False
    ENCODE_VIDEO = False

    DOWNLOAD_URL_HINT = (
        'For ardmediathek.de use the player link, for example\n'
        'https://www.ardmediathek.de/video/<title>/<id>\n'
        'instead of the topic page\n'
        'https://www.ardmediathek.de/film/<title>/<id>'
    )

    def build_config(
        self, media_type: DownMediaType, curr_tmp_dir: Path
    ) -> ArdHostModel:
        return ArdHostModel(
            hostnames=self.HOSTNAMES,
            encode_audio=self.ENCODE_AUDIO,
            encode_video=self.ENCODE_VIDEO,
            ffmpeg_audio_opts=self.FFMPEG_AUDIO_OPTS,
            ffmpeg_video_opts=self.FFMPEG_VIDEO_OPTS,
            ytdl_opts=self._build_ytdl_opts(media_type, curr_tmp_dir),
        )

    def download_url_hint(self) -> str | None:
        """Name the '/video/' link behind a topic page 'yt-dlp' cannot read.

        A '/film/' page carries the id of the grouping that holds the film rather
        than the id of the film itself, and no extractor matches its path either, so
        the download never had a chance. Resolve that id through the API the site
        uses and spell out the links that do work.
        """
        asset_id = self._asset_id()
        if not asset_id or self._url_prefix() in _SUPPORTED_PREFIXES:
            # Already a shape 'yt-dlp' handles, so the failure is something else and
            # a hint about the URL would only mislead.
            return None

        items = self._resolve_items(asset_id)
        if not items:
            return self.DOWNLOAD_URL_HINT

        slug = self._title_slug() or 'video'
        lines = ['This page cannot be downloaded, but these can. Send one of them:']
        for item_id, title in items[:_MAX_LISTED_ITEMS]:
            url = _VIDEO_PAGE_TPL.format(slug=slug, asset_id=item_id)
            lines.append(f'\n{title}\n{url}')
        return '\n'.join(lines)

    def _resolve_items(self, asset_id: str) -> list[tuple[str, str]]:
        """Return (asset_id, title) pairs for the videos this URL stands for."""
        item = fetch_json(_ITEM_API_TPL.format(asset_id=asset_id))
        if item:
            # The id is a video after all and only the path prefix was wrong, so the
            # same id under '/video/' is the link to send.
            title = item.get('title') or 'This video'
            return [(asset_id, title)]

        # No video with that id, so it is a grouping. Ask for its contents.
        asset = fetch_json(_ASSET_API_TPL.format(asset_id=asset_id))
        items: list[tuple[str, str]] = []
        for teaser in (asset or {}).get('teasers') or []:
            if not isinstance(teaser, dict):
                continue
            teaser_id = teaser.get('id')
            title = teaser.get('longTitle') or teaser.get('title')
            if teaser_id and title:
                items.append((teaser_id, title))
        self._log.info('Resolved ardmediathek.de items for "%s": %s', self.url, items)
        return items

    def _path_segments(self) -> list[str]:
        return [segment for segment in urlsplit(self.url).path.split('/') if segment]

    def _url_prefix(self) -> str | None:
        """First path segment, which is what decides the extractor."""
        segments = self._path_segments()
        return segments[0] if segments else None

    def _asset_id(self) -> str | None:
        """Trailing path segment, if it looks like an asset id."""
        segments = self._path_segments()
        if not segments or self._url_prefix() in _PLAYLIST_PREFIXES:
            return None
        candidate = segments[-1]
        return candidate if _ASSET_ID_RE.match(candidate) else None

    def _title_slug(self) -> str | None:
        """Return the URL's human-readable segment, so the hint stays readable."""
        segments = self._path_segments()
        return segments[-2] if len(segments) > 1 else None

    def _build_custom_ytdl_video_opts(self) -> tuple[str, ...]:
        return self.DEFAULT_VIDEO_FORMAT_SORT_OPT
