"""Minimal HTTP helpers for building failure hints.

Only used on the failure path, where a host config inspects the site to work out
which link would have worked. Everything here returns 'None' instead of raising:
a hint is a convenience and must never replace the real download error.
"""

import json
import logging
import urllib.error
import urllib.request
from typing import Final

_LOG: Final[logging.Logger] = logging.getLogger(__name__)

DEFAULT_TIMEOUT: Final[int] = 8
USER_AGENT: Final[str] = 'Mozilla/5.0'


def fetch_text(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """Return the body of 'url', or 'None' if it could not be read."""
    request = urllib.request.Request(  # noqa: S310 # Caller builds an https URL.
        url, headers={'User-Agent': USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.read().decode('utf-8', errors='replace')
    except (urllib.error.URLError, OSError, ValueError) as err:
        _LOG.debug('Could not fetch "%s" for the hint: %s', url, err)
        return None


def fetch_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict | None:
    """Return the JSON object at 'url', or 'None' if it is missing or not an object."""
    raw = fetch_text(url, timeout=timeout)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None
