import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

from yt_shared.constants import KIKA_HOSTS
from yt_shared.enums import DownMediaType

from ytdl_opts.per_host._base import AbstractHostConfig, BaseHostConfModel
from ytdl_opts.per_host._registry import HostConfRegistry

_API_ROOT: Final[str] = 'https://www.kika.de/ackley/v1'
_BRAND_PAGE_TPL: Final[str] = 'https://www.kika.de/{slug}/{brand_id}'
_EPISODE_API_URL_RE: Final[re.Pattern[str]] = re.compile(
    rf'{re.escape(_API_ROOT)}/videos/[\w-]+'
)

_HTTP_TIMEOUT: Final[int] = 8
_USER_AGENT: Final[str] = 'Mozilla/5.0'
# Bounds on the work done while building the hint, so a failing download never turns
# into a long crawl of the site.
_MAX_HTTP_CALLS: Final[int] = 20
_MAX_PROBED_EPISODES: Final[int] = 5
_MAX_LISTED_BRANDS: Final[int] = 6
# A show is split into one brand per season, numbered in steps of two. Episodes only
# reveal the brand they belong to, so the siblings have to be probed for.
_PROBED_BRAND_SUFFIXES: Final[tuple[int, ...]] = (100, 102, 104, 106, 108)


class KikaHostModel(BaseHostConfModel):
    pass


class KikaHost(AbstractHostConfig, metaclass=HostConfRegistry):
    ALLOW_NULL_HOSTNAMES = False
    HOSTNAMES = KIKA_HOSTS
    ENCODE_AUDIO = False
    ENCODE_VIDEO = False

    # Budget for the HTTP calls made while building the hint, reset per attempt.
    _http_calls: int = 0

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

    def playlist_url_hint(self) -> str | None:
        """Name the show pages behind an episode listing that could not be read.

        A kika.de listing page aggregates several seasons and 'yt-dlp' cannot read it,
        while each season has its own show page that it reads fine. Those pages are not
        linked anywhere obvious, so work them out and spell them out.
        """
        self._http_calls = 0
        brands = self._find_brands()
        if not brands:
            return self.PLAYLIST_URL_HINT

        slug = self._show_slug() or 'kika'
        lines = ['This page cannot be read, but these can. Send one per series:']
        for brand_id, title in brands[:_MAX_LISTED_BRANDS]:
            url = _BRAND_PAGE_TPL.format(slug=slug, brand_id=brand_id)
            lines.append(f'\n{title}\n/series {url}')
        return '\n'.join(lines)

    def _find_brands(self) -> list[tuple[str, str]]:
        """Return (brand_id, title) pairs for the series behind this listing page."""
        brand_ids = self._brand_ids_from_episodes() | self._probed_sibling_brand_ids()

        brands: list[tuple[str, str]] = []
        for brand_id in sorted(brand_ids):
            brand = self._get_json(f'{_API_ROOT}/brands/{brand_id}')
            title = (brand or {}).get('title')
            if title:
                brands.append((brand_id, title))
        self._log.info('Resolved kika.de brands for "%s": %s', self.url, brands)
        return brands

    def _brand_ids_from_episodes(self) -> set[str]:
        """Collect the brands the episodes listed on the page belong to."""
        page = self._get_text(self.url)
        if not page:
            return set()

        # The page embeds its JSON with escaped slashes.
        episode_urls = dict.fromkeys(
            _EPISODE_API_URL_RE.findall(page.replace('\\/', '/'))
        )
        brand_ids: set[str] = set()
        for episode_url in list(episode_urls)[:_MAX_PROBED_EPISODES]:
            episode = self._get_json(episode_url)
            brand_id = ((episode or {}).get('brand') or {}).get('id')
            if brand_id:
                brand_ids.add(brand_id)
        return brand_ids

    def _probed_sibling_brand_ids(self) -> set[str]:
        """Guess the show's other season brands from its URL slug."""
        slug = self._show_slug()
        if not slug:
            return set()
        return {f'{slug}-{suffix}' for suffix in _PROBED_BRAND_SUFFIXES}

    def _show_slug(self) -> str | None:
        """First path segment of the URL, which is the show's own slug."""
        segments = [s for s in urlsplit(self.url).path.split('/') if s]
        return segments[0] if segments else None

    def _get_text(self, url: str) -> str | None:
        if self._http_calls >= _MAX_HTTP_CALLS:
            return None
        self._http_calls += 1
        request = urllib.request.Request(  # noqa: S310 # https URL built above.
            url, headers={'User-Agent': _USER_AGENT}
        )
        try:
            with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT) as response:  # noqa: S310
                return response.read().decode('utf-8', errors='replace')
        except (urllib.error.URLError, OSError, ValueError) as err:
            self._log.debug('Could not fetch "%s" for the hint: %s', url, err)
            return None

    def _get_json(self, url: str) -> dict | None:
        raw = self._get_text(url)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except ValueError:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _build_custom_ytdl_video_opts(self) -> tuple[str, ...]:
        # KiKA serves every resolution both as HLS and as a plain MP4. Prefer the
        # plain file: it is a single request instead of several hundred fragments,
        # at the same resolution, which makes a long series far less likely to fail.
        return '--format-sort', 'res,proto:https,vcodec:h265,h264'
