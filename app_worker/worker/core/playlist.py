"""Playlist/series expansion module.

Instead of downloading a series URL as one media file, its entries are listed with
`yt-dlp`'s flat extraction and each entry is later queued as a separate download task.
"""

import logging
from dataclasses import dataclass, field

import yt_dlp

from worker.core.exceptions import PlaylistExtractorError
from ytdl_opts.per_host._base import AbstractHostConfig


@dataclass(frozen=True, slots=True)
class PlaylistEntry:
    url: str
    title: str | None = None


@dataclass(frozen=True, slots=True)
class Playlist:
    url: str
    title: str | None
    total_count: int
    entries: list[PlaylistEntry] = field(default_factory=list)
    """Entries to download, capped by the configured maximum."""


class PlaylistExtractor:
    """Extract playlist/series entries without downloading any media."""

    _PLAYLIST_TYPE = 'playlist'
    _URL_KEYS = ('webpage_url', 'url', 'original_url')

    _INVALID_URL_MSG = (
        'Invalid series URL: no series, season or playlist could be read from this '
        'link. Use the show or series overview page, not an episode listing page.'
    )
    _SINGLE_VIDEO_MSG = (
        'This link is a single video, not a series, season or playlist. '
        'Send it without the /series command to download it.'
    )

    def __init__(self) -> None:
        self._log = logging.getLogger(self.__class__.__name__)

    def extract(self, host_conf: AbstractHostConfig, max_items: int) -> Playlist:
        url = host_conf.url
        ytdl_opts = host_conf.build_playlist_ytdl_opts()
        self._log.info('Listing playlist "%s" with options: %s', url, ytdl_opts)

        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            meta: dict | None = ytdl.extract_info(url, download=False)

        if not meta:
            err_msg = self._invalid_url_error(host_conf)
            self._log.error('%s Meta: %s', err_msg, meta)
            raise PlaylistExtractorError(err_msg)

        if meta.get('_type') != self._PLAYLIST_TYPE:
            raise PlaylistExtractorError(self._SINGLE_VIDEO_MSG)

        entries = self._flatten_entries(meta)
        if not entries:
            raise PlaylistExtractorError('Playlist does not contain any video')

        total_count = len(entries)
        if total_count > max_items:
            self._log.warning(
                'Playlist "%s" has %d entries, limiting to %d',
                url,
                total_count,
                max_items,
            )
            entries = entries[:max_items]

        self._log.info('Playlist "%s" expanded to %d entries', url, len(entries))
        return Playlist(
            url=url,
            title=meta.get('title'),
            total_count=total_count,
            entries=entries,
        )

    def _invalid_url_error(self, host_conf: AbstractHostConfig) -> str:
        """Build the error text, adding the host's hint about the right link."""
        if host_conf.PLAYLIST_URL_HINT:
            return f'{self._INVALID_URL_MSG}\n\n{host_conf.PLAYLIST_URL_HINT}'
        return self._INVALID_URL_MSG

    def _flatten_entries(self, meta: dict) -> list[PlaylistEntry]:
        """Collect entries of a playlist, descending into nested playlists."""
        entries: list[PlaylistEntry] = []
        seen_urls: set[str] = set()

        for entry in self._walk(meta):
            if entry.url in seen_urls:
                self._log.debug('Skipping duplicate playlist entry %s', entry.url)
                continue
            seen_urls.add(entry.url)
            entries.append(entry)
        return entries

    def _walk(self, meta: dict) -> list[PlaylistEntry]:
        entries: list[PlaylistEntry] = []
        for entry in meta.get('entries') or []:
            if not entry:
                # 'yt-dlp' yields None for entries it failed to extract.
                continue
            if entry.get('_type') == self._PLAYLIST_TYPE and entry.get('entries'):
                entries.extend(self._walk(entry))
                continue

            url = self._get_entry_url(entry)
            if not url:
                self._log.warning('Playlist entry without URL, skipping: %s', entry)
                continue
            entries.append(PlaylistEntry(url=url, title=entry.get('title')))
        return entries

    def _get_entry_url(self, entry: dict) -> str | None:
        for key in self._URL_KEYS:
            url = entry.get(key)
            if url:
                return url
        return None
