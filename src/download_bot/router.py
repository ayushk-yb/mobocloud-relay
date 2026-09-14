"""Decides which backend (Transmission or aria2) a link should go to.

This module only classifies strings; it never executes them. No shell
involvement anywhere in this file or its callers.
"""

from __future__ import annotations

import re

MAGNET_RE = re.compile(r"^magnet:\?xt=urn:[a-z0-9]+:[a-zA-Z0-9]+", re.IGNORECASE)
HTTP_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

TRANSMISSION = "transmission"
ARIA2 = "aria2"


class UnrecognizedLink(ValueError):
    pass


def classify(link: str) -> str:
    """Return TRANSMISSION or ARIA2 for a bare (no /t or /a prefix) link."""
    link = link.strip()
    if MAGNET_RE.match(link):
        return TRANSMISSION
    if HTTP_URL_RE.match(link):
        if link.lower().split("?")[0].endswith(".torrent"):
            return TRANSMISSION
        return ARIA2
    raise UnrecognizedLink(
        "That doesn't look like a magnet link or an http(s) URL. "
        "Send a magnet:?xt=... link, a direct URL, or use /t or /a explicitly."
    )


def is_link_like(text: str) -> bool:
    text = text.strip()
    return bool(MAGNET_RE.match(text) or HTTP_URL_RE.match(text))
