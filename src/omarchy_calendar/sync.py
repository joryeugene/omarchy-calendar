# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from .cache import CalendarStore
from .http import HttpError, ReadOnlyHttp
from .keyring import SecretServiceStore, redact
from .models import ProviderHealth
from .providers.google import GoogleProvider
from .providers.microsoft import MicrosoftProvider
from .settings import ProviderSettings


TOKEN_ENDPOINTS = {
    "google": "https://oauth2.googleapis.com/token",
    "microsoft": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
}


class SyncEngine:
    def __init__(
        self,
        store: CalendarStore,
        *,
        keyring: Any | None = None,
        settings: ProviderSettings | None = None,
        providers: dict[str, Any] | None = None,
        http: Any | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.store = store
        self.keyring = keyring or SecretServiceStore()
        self.settings = settings or ProviderSettings.load()
        self.http = http or ReadOnlyHttp()
        self.providers = providers or {
            "google": GoogleProvider(self.http),
            "microsoft": MicrosoftProvider(self.http),
        }
        self.now = now or (lambda: datetime.now(timezone.utc))

    def sync(self, provider: str | None = None) -> dict[str, object]:
        selected = self.store.accounts(provider)
        result: dict[str, object] = {"synced": 0, "failed": 0, "skipped": 0, "accounts": []}
        for account in selected:
            if not account["connected"]:
                result["skipped"] = int(result["skipped"]) + 1
                continue
            name = str(account["provider"])
            account_id = str(account["account_id"])
            try:
                token = self.keyring.get(name, account_id)
                if token is None:
                    raise HttpError(401, "Calendar credentials are missing")
                token = self._refresh_if_needed(name, account_id, token)
                start, end = self.window()
                live_account, events = self.providers[name].fetch_window(str(token["access_token"]), start, end)
                health = ProviderHealth.ok(name, live_account.account_id, self.now().isoformat())
                self.store.replace_window(name, live_account.account_id, start, end, events, health)
                result["synced"] = int(result["synced"]) + 1
                result["accounts"].append({"provider": name, "account_id": live_account.account_id, "events": len(events)})
            except HttpError as error:
                existing = self.store.health(name, account_id) or ProviderHealth(
                    provider=name, account_id=account_id, connected=True, last_sync=""
                )
                self.store.set_health(replace(
                    existing,
                    connected=error.status != 401,
                    stale=True,
                    last_error=redact(str(error)),
                    retry_after=error.retry_after,
                ))
                result["failed"] = int(result["failed"]) + 1
                result["accounts"].append({"provider": name, "account_id": account_id, "error": redact(str(error))})
        return result

    def window(self) -> tuple[str, str]:
        current = self.now()
        return (current - timedelta(days=30)).isoformat(), (current + timedelta(days=90)).isoformat()

    def _refresh_if_needed(self, provider: str, account_id: str, token: dict[str, Any]) -> dict[str, Any]:
        expires_at = float(token.get("expires_at") or 0)
        if expires_at > self.now().timestamp() + 60:
            return token
        refresh_token = str(token.get("refresh_token") or "")
        client_id = self.settings.client_id(provider)
        if not refresh_token or not client_id:
            raise HttpError(401, "Calendar credentials need browser reconnection")
        form = {
            "client_id": client_id,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        if provider == "google":
            app_credential = self.settings.google_app_credential(self.keyring)
            if not app_credential:
                raise HttpError(401, "Google Desktop credentials are not configured")
            form["client_secret"] = app_credential
        response = self.http.post_token(TOKEN_ENDPOINTS[provider], form)
        merged = dict(token)
        merged.update(response)
        merged["refresh_token"] = str(response.get("refresh_token") or refresh_token)
        merged["expires_at"] = self.now().timestamp() + int(response.get("expires_in") or 3600)
        self.keyring.put(provider, account_id, merged)
        return merged
