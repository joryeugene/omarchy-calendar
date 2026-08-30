# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable
import webbrowser

from .cache import CalendarStore
from .http import ReadOnlyHttp
from .keyring import SecretServiceStore
from .models import ProviderHealth
from .oauth import GOOGLE_SCOPES, MICROSOFT_SCOPES, LoopbackReceiver, OAuthFlow, authorization_url
from .providers.google import GoogleProvider
from .providers.microsoft import MicrosoftProvider
from .settings import ProviderSettings
from .sync import TOKEN_ENDPOINTS


class Authenticator:
    def __init__(
        self,
        store: CalendarStore,
        *,
        keyring: Any | None = None,
        http: Any | None = None,
        settings: ProviderSettings | None = None,
        providers: dict[str, Any] | None = None,
        browser: Callable[[str], bool] = webbrowser.open,
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

    def authenticate(self, provider: str) -> dict[str, object]:
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
            url = authorization_url(provider, client_id, receiver.redirect_uri, flow)
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
        if provider == "google":
            form["client_secret"] = app_credential
        else:
            form["scope"] = " ".join(MICROSOFT_SCOPES)
        response = self.http.post_token(TOKEN_ENDPOINTS[provider], form)
        token = dict(response)
        token["expires_at"] = self.now().timestamp() + int(response.get("expires_in") or 3600)
        start = (self.now() - timedelta(days=30)).isoformat()
        end = (self.now() + timedelta(days=90)).isoformat()
        account, events = self.providers[provider].fetch_window(str(token["access_token"]), start, end)
        self.keyring.put(provider, account.account_id, token)
        self.store.replace_window(
            provider, account.account_id, start, end, events,
            ProviderHealth.ok(provider, account.account_id, self.now().isoformat()),
        )
        self.store.clear_demo()
        return {
            "provider": provider,
            "account_id": account.account_id,
            "account_label": account.label,
            "events": len(events),
        }
