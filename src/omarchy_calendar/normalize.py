# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from urllib.parse import urlparse


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")


def plain_text(source: str, limit: int = 4000) -> str:
    parser = _TextExtractor()
    parser.feed(str(source or ""))
    parser.close()
    text = html.unescape("".join(parser.parts))
    return re.sub(r"\s+", " ", text).strip()[:limit]


_URL = re.compile(r"https://[^\s<>()\"']+", re.IGNORECASE)
_MEETING_HOSTS = (
    "meet.google.com",
    "teams.microsoft.com",
    "zoom.us",
    "webex.com",
    "meet.jit.si",
    "whereby.com",
)


def is_safe_https_url(value: str) -> bool:
    parsed = urlparse(str(value or ""))
    return parsed.scheme == "https" and bool(parsed.netloc) and not parsed.username and not parsed.password


def is_recognized_meeting_url(value: str) -> bool:
    if not is_safe_https_url(value):
        return False
    host = (urlparse(value).hostname or "").lower()
    return any(host == allowed or host.endswith("." + allowed) for allowed in _MEETING_HOSTS)


def extract_meeting_url(*sources: str) -> str:
    for source in sources:
        for match in _URL.findall(str(source or "")):
            candidate = match.rstrip(".,;:!?]}\"")
            if is_recognized_meeting_url(candidate):
                return candidate
    return ""
