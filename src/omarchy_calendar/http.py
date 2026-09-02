# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

from . import __version__
from .keyring import redact


MAX_RESPONSE = 16 * 1024 * 1024


class ReadOnlyViolation(RuntimeError):
    pass


@dataclass(slots=True)
class HttpError(RuntimeError):
    status: int
    message: str
    retry_after: str = ""

    def __str__(self) -> str:
        return self.message


class ReadOnlyHttp:
    def __init__(self, opener: Any | None = None, *, timeout: int = 20):
        self.opener = opener or urllib.request.build_opener()
        self.timeout = timeout

    def get_json(self, url: str, headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        return self.request_json("GET", url, headers=headers)

    def post_token(self, url: str, form: Mapping[str, str]) -> dict[str, Any]:
        if not self._is_token_endpoint(url):
            raise ReadOnlyViolation("POST is limited to approved OAuth token endpoints")
        return self.request_json("POST", url, form, headers={"Content-Type": "application/x-www-form-urlencoded"})

    def request_json(
        self,
        method: str,
        url: str,
        body: Mapping[str, str] | None = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        if method == "GET":
            data = None
        elif method == "POST" and self._is_token_endpoint(url):
            data = urllib.parse.urlencode(body or {}).encode("utf-8")
        else:
            raise ReadOnlyViolation(f"{method} is not allowed for calendar provider data")
        if urllib.parse.urlparse(url).scheme != "https":
            raise ReadOnlyViolation("Provider requests require HTTPS")
        request_headers = {
            "Accept": "application/json",
            "User-Agent": f"omarchy-calendar/{__version__}",
            **dict(headers or {}),
        }
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise HttpError(0, "Provider response exceeded the safe size limit")
                payload = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as error:
            raw = error.read(16_384).decode("utf-8", "replace")
            retry_after = error.headers.get("Retry-After", "") if error.headers else ""
            raise HttpError(error.code, redact(raw) or f"Provider returned HTTP {error.code}", retry_after) from error
        except urllib.error.URLError as error:
            raise HttpError(0, redact(str(error.reason))) from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise HttpError(0, "Provider returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise HttpError(0, "Provider returned a non-object JSON response")
        return payload

    @staticmethod
    def _is_token_endpoint(url: str) -> bool:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https":
            return False
        if parsed.netloc == "oauth2.googleapis.com":
            return parsed.path == "/token"
        if parsed.netloc == "login.microsoftonline.com":
            return parsed.path.endswith("/oauth2/v2.0/token")
        return False
