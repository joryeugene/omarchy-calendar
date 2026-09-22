# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import os
import shlex
import shutil
import subprocess
import webbrowser

from .cache import CalendarStore
from .http import ReadOnlyHttp
from .keyring import SecretServiceStore
from .models import ProviderHealth
from .oauth import (
    GOOGLE_EDIT_SCOPES,
    GOOGLE_SCOPES,
    MICROSOFT_EDIT_SCOPES,
    MICROSOFT_SCOPES,
    LoopbackReceiver,
    OAuthFlow,
    authorization_url,
)
from .providers.google import GoogleProvider
from .providers.microsoft import MicrosoftProvider
from .settings import ProviderSettings
from .sync import TOKEN_ENDPOINTS


def _spawn_browser(argv: list[str]) -> bool:
    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def open_system_browser(url: str) -> bool:
    """Open the authorization URL in the user's browser.

    Omarchy's launcher raises and focuses the existing browser window, which
    plain ``xdg-open`` and ``webbrowser`` do not. Prefer it, then ``xdg-open``,
    then the standard library, so a browser always comes to the front for the
    consent step. ``OMARCHY_CALENDAR_BROWSER_COMMAND`` overrides the chain.
    """
    override = os.environ.get("OMARCHY_CALENDAR_BROWSER_COMMAND", "").strip()
    if override:
        return _spawn_browser(shlex.split(override) + [url])
    launcher = shutil.which("omarchy-launch-browser")
    if launcher:
        return _spawn_browser([launcher, url])
    xdg_open = shutil.which("xdg-open")
    if xdg_open:
        return _spawn_browser([xdg_open, url])
    return webbrowser.open(url)


class Authenticator:
    def __init__(
        self,
        store: CalendarStore,
        *,
        keyring: Any | None = None,
        http: Any | None = None,
        settings: ProviderSettings | None = None,
        providers: dict[str, Any] | None = None,
        browser: Callable[[str], bool] = open_system_browser,
        receiver_factory: Callable[[OAuthFlow], Any] = LoopbackReceiver,
        flow_factory: Callable[[], OAuthFlow] = OAuthFlow.create,
        now: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.keyring = keyring or SecretServiceStore()
        self.http = http or ReadOnlyHttp()
        self.settings = settings or ProviderSettings.load()
        self.providers = providers or {
            "google": GoogleProvider(self.http),
            "microsoft": MicrosoftProvider(self.http),
        }
        self.browser = browser
        self.receiver_factory = receiver_factory
        self.flow_factory = flow_factory
        self.now = now or (lambda: datetime.now(timezone.utc))

    def authenticate(
        self,
        provider: str,
        *,
        access: str = "read",
        expected_account_id: str = "",
    ) -> dict[str, object]:
        client_id = self.settings.client_id(provider)
        if not client_id:
            raise ValueError(f"{provider} public client ID is not configured")
        app_credential = ""
        if provider == "google":
            app_credential = self.settings.google_app_credential(self.keyring)
            if not app_credential:
                raise ValueError("Google Desktop credentials are not configured")
        flow = self.flow_factory()
        with self.receiver_factory(flow, provider) as receiver:
            url = authorization_url(provider, client_id, receiver.redirect_uri, flow, access=access)
            if not self.browser(url):
                raise RuntimeError("Could not open the browser for calendar authorization")
            code = receiver.wait(timeout=600)
        form = {
            "client_id": client_id,
            "code": code,
            "code_verifier": flow.verifier,
            "redirect_uri": receiver.redirect_uri,
            "grant_type": "authorization_code",
        }
        requested_scopes = (
            GOOGLE_EDIT_SCOPES if provider == "google" and access == "edit"
            else GOOGLE_SCOPES if provider == "google"
            else MICROSOFT_EDIT_SCOPES if access == "edit"
            else MICROSOFT_SCOPES
        )
        if provider == "google":
            form["client_secret"] = app_credential
        else:
            form["scope"] = " ".join(requested_scopes)
        response = self.http.post_token(TOKEN_ENDPOINTS[provider], form)
        granted_scope = str(response.get("scope") or " ".join(requested_scopes))
        if access == "edit":
            write_scope = (
                GOOGLE_EDIT_SCOPES[-1]
                if provider == "google" else MICROSOFT_EDIT_SCOPES[-1]
            )
            if write_scope not in set(granted_scope.split()):
                label = "Google" if provider == "google" else "Outlook"
                raise PermissionError(f"{label} did not grant read and edit permission")
        token = dict(response)
        token["scope"] = granted_scope
        token["expires_at"] = self.now().timestamp() + int(response.get("expires_in") or 3600)
        token["access_mode"] = access
        start = (self.now() - timedelta(days=30)).isoformat()
        end = (self.now() + timedelta(days=90)).isoformat()
        fetched = self.providers[provider].fetch_window(str(token["access_token"]), start, end)
        if len(fetched) == 3:
            account, calendars, events = fetched
        else:
            account, events = fetched
            calendars = None
        if expected_account_id and account.account_id != expected_account_id:
            label = "Google" if provider == "google" else "Outlook"
            raise ValueError(f"Choose the same {label} account to enable editing")
        previous = self.keyring.get(provider, account.account_id) or {}
        if not token.get("refresh_token") and previous.get("refresh_token"):
            token["refresh_token"] = previous["refresh_token"]
        self.keyring.put(provider, account.account_id, token)
        self.store.replace_window(
            provider, account.account_id, start, end, events,
            ProviderHealth.ok(provider, account.account_id, self.now().isoformat()),
            calendars=calendars,
        )
        self.store.clear_demo()
        return {
            "provider": provider,
            "account_id": account.account_id,
            "account_label": account.label,
            "events": len(events),
            "access": access,
        }
