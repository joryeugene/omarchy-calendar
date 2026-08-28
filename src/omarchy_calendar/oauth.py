# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import base64
import hashlib
import html
import secrets
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Mapping, Sequence
from urllib.parse import parse_qs, urlencode, urlparse


GOOGLE_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.events.readonly",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
)

MICROSOFT_SCOPES = (
    "openid",
    "profile",
    "offline_access",
    "User.Read",
    "Calendars.Read",
)


class OAuthError(RuntimeError):
    pass


class OAuthStateError(OAuthError):
    pass


def _first(parameters: Mapping[str, Sequence[str] | str], name: str) -> str:
    value = parameters.get(name, "")
    if isinstance(value, str):
        return value
    return value[0] if value else ""


@dataclass(frozen=True, slots=True)
class OAuthFlow:
    verifier: str
    state: str

    @classmethod
    def create(cls) -> "OAuthFlow":
        return cls(
            verifier=secrets.token_urlsafe(64),
            state=secrets.token_urlsafe(32),
        )

    @classmethod
    def for_test(cls, *, verifier: str, state: str) -> "OAuthFlow":
        return cls(verifier=verifier, state=state)

    @property
    def challenge(self) -> str:
        digest = hashlib.sha256(self.verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    def verify_callback(self, parameters: Mapping[str, Sequence[str] | str]) -> str:
        if not secrets.compare_digest(_first(parameters, "state"), self.state):
            raise OAuthStateError("OAuth callback state did not match")
        provider_error = _first(parameters, "error")
        if provider_error:
            detail = _first(parameters, "error_description") or provider_error
            raise OAuthError(f"Provider rejected authorization: {detail}")
        code = _first(parameters, "code")
        if not code:
            raise OAuthError("OAuth callback did not contain an authorization code")
        return code


def authorization_url(
    provider: str,
    client_id: str,
    redirect_uri: str,
    flow: OAuthFlow,
) -> str:
    common = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": flow.state,
        "code_challenge": flow.challenge,
        "code_challenge_method": "S256",
    }
    if provider == "google":
        common.update({
            "scope": " ".join(GOOGLE_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        })
        base = "https://accounts.google.com/o/oauth2/v2/auth"
    elif provider == "microsoft":
        common.update({
            "scope": " ".join(MICROSOFT_SCOPES),
            "response_mode": "query",
        })
        base = "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize"
    else:
        raise ValueError(f"unsupported provider: {provider}")
    return f"{base}?{urlencode(common)}"


class LoopbackReceiver:
    def __init__(self, flow: OAuthFlow, provider: str = "google"):
        self.flow = flow
        if provider not in ("google", "microsoft"):
            raise ValueError(f"unsupported provider: {provider}")
        self.provider = provider
        self.callback_path = "/" if provider == "microsoft" else "/callback"
        self.code = ""
        self.error: Exception | None = None
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != receiver.callback_path:
                    self.send_error(404)
                    return
                try:
                    receiver.code = receiver.flow.verify_callback(parse_qs(parsed.query))
                    status = 200
                    message = "Calendar connected. You can close this tab."
                except Exception as error:  # stored and re-raised by wait
                    receiver.error = error
                    status = 400
                    message = "Calendar connection failed. Return to the calendar panel."
                body = (
                    "<!doctype html><meta charset=utf-8>"
                    "<title>Omarchy Calendar</title>"
                    f"<p>{html.escape(message)}</p>"
                ).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, _format: str, *_args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.timeout = 0.25

    @property
    def redirect_uri(self) -> str:
        port = self.server.server_address[1]
        if self.provider == "microsoft":
            return f"http://localhost:{port}"
        return f"http://127.0.0.1:{port}/callback"

    def wait(self, timeout: float = 180) -> str:
        import time

        deadline = time.monotonic() + timeout
        while not self.code and self.error is None and time.monotonic() < deadline:
            self.server.handle_request()
        if self.error is not None:
            raise self.error
        if not self.code:
            raise OAuthError("OAuth browser login timed out")
        return self.code

    def close(self) -> None:
        self.server.server_close()

    def __enter__(self) -> "LoopbackReceiver":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
