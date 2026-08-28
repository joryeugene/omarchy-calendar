# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from typing import Any


class KeyringError(RuntimeError):
    pass


_SECRET_KEYS = ("access_token", "refresh_token", "id_token", "client_secret", "code")


def redact(text: str) -> str:
    cleaned = str(text)
    for key in _SECRET_KEYS:
        cleaned = re.sub(
            rf"(?i)([\"']?{re.escape(key)}[\"']?\s*[:=]\s*[\"']?)([^\s&;,\"'}}]+)",
            rf"\1[redacted]",
            cleaned,
        )
    return cleaned


class SecretServiceStore:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run):
        self.runner = runner

    @staticmethod
    def _attributes(provider: str, account_id: str) -> list[str]:
        return [
            "application", "omarchy-calendar",
            "provider", provider,
            "account", account_id,
        ]

    @staticmethod
    def _app_credential_attributes(provider: str) -> list[str]:
        if provider != "google":
            raise ValueError(f"unsupported app credential provider: {provider}")
        return [
            "application", "omarchy-calendar",
            "provider", provider,
            "kind", "oauth-client-credential",
        ]

    def put(self, provider: str, account_id: str, token: dict[str, Any]) -> None:
        argv = [
            "secret-tool",
            "store",
            f"--label=Omarchy Calendar {provider} {account_id}",
            *self._attributes(provider, account_id),
        ]
        result = self._run(argv, input=json.dumps(token, separators=(",", ":")))
        if result.returncode != 0:
            raise KeyringError(redact(result.stderr or "Secret Service store failed"))

    def get(self, provider: str, account_id: str) -> dict[str, Any] | None:
        argv = ["secret-tool", "lookup", *self._attributes(provider, account_id)]
        result = self._run(argv)
        if result.returncode == 1:
            return None
        if result.returncode != 0:
            raise KeyringError(redact(result.stderr or "Secret Service lookup failed"))
        try:
            payload = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise KeyringError("Secret Service returned invalid token data") from error
        if not isinstance(payload, dict):
            raise KeyringError("Secret Service returned invalid token data")
        return payload

    def put_app_credential(self, provider: str, credential: str) -> None:
        value = str(credential).strip()
        if not value or len(value) > 2048 or not value.isprintable():
            raise ValueError("OAuth app credential must be one printable line")
        argv = [
            "secret-tool", "store",
            "--label=Omarchy Calendar Google Desktop app credential",
            *self._app_credential_attributes(provider),
        ]
        result = self._run(argv, input=value)
        if result.returncode != 0:
            raise KeyringError(redact(result.stderr or "Secret Service store failed"))

    def get_app_credential(self, provider: str) -> str:
        argv = ["secret-tool", "lookup", *self._app_credential_attributes(provider)]
        result = self._run(argv)
        if result.returncode == 1:
            return ""
        if result.returncode != 0:
            raise KeyringError(redact(result.stderr or "Secret Service lookup failed"))
        return str(result.stdout).strip()

    def clear(self, provider: str, account_id: str) -> None:
        argv = ["secret-tool", "clear", *self._attributes(provider, account_id)]
        result = self._run(argv)
        if result.returncode not in (0, 1):
            raise KeyringError(redact(result.stderr or "Secret Service clear failed"))

    def clear_provider(self, provider: str) -> None:
        if provider not in ("google", "microsoft"):
            raise ValueError(f"unsupported provider: {provider}")
        result = self._run([
            "secret-tool", "clear",
            "application", "omarchy-calendar",
            "provider", provider,
        ])
        if result.returncode not in (0, 1):
            raise KeyringError(redact(result.stderr or "Secret Service clear failed"))

    def clear_all(self) -> None:
        result = self._run([
            "secret-tool", "clear", "application", "omarchy-calendar"
        ])
        if result.returncode not in (0, 1):
            raise KeyringError(redact(result.stderr or "Secret Service clear failed"))

    def _run(self, argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        try:
            return self.runner(
                argv,
                text=True,
                capture_output=True,
                check=False,
                **kwargs,
            )
        except FileNotFoundError as error:
            raise KeyringError("Secret Service client is not installed") from error
