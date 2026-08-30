# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path


BUNDLED_PUBLIC_CLIENT_IDS = {
    "google": "",
    "microsoft": "9a7f1138-b541-4840-aa23-e84297de342d",
}
BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL = ""


def default_settings_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "omarchy-calendar" / "providers.json"


@dataclass(frozen=True, slots=True)
class ProviderSettings:
    google_client_id: str = ""
    microsoft_client_id: str = ""

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ProviderSettings":
        config_path = Path(path) if path is not None else default_settings_path()
        if not config_path.is_file():
            return cls()
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        return cls(
            google_client_id=str(payload.get("google", {}).get("client_id", "")).strip(),
            microsoft_client_id=str(payload.get("microsoft", {}).get("client_id", "")).strip(),
        )

    @classmethod
    def clear(cls, path: str | Path | None = None) -> bool:
        config_path = Path(path) if path is not None else default_settings_path()
        if not config_path.exists() and not config_path.is_symlink():
            return False
        config_path.unlink()
        return True

    def client_id(self, provider: str) -> str:
        if provider == "google":
            return self.google_client_id or BUNDLED_PUBLIC_CLIENT_IDS[provider]
        if provider == "microsoft":
            return self.microsoft_client_id or BUNDLED_PUBLIC_CLIENT_IDS[provider]
        raise ValueError(f"unsupported provider: {provider}")

    def google_app_credential(self, keyring: object) -> str:
        if self.google_client_id:
            getter = getattr(keyring, "get_app_credential")
            return str(getter("google") or "").strip()
        if BUNDLED_PUBLIC_CLIENT_IDS["google"]:
            return BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL.strip()
        return ""

    def registration_source(self, provider: str) -> str:
        if provider == "google":
            local_client_id = self.google_client_id
        elif provider == "microsoft":
            local_client_id = self.microsoft_client_id
        else:
            raise ValueError(f"unsupported provider: {provider}")
        if local_client_id:
            return "local"
        return "bundled" if BUNDLED_PUBLIC_CLIENT_IDS[provider] else ""

    def with_client_id(self, provider: str, client_id: str) -> "ProviderSettings":
        if provider not in ("google", "microsoft"):
            raise ValueError(f"unsupported provider: {provider}")
        value = _validate_public_client_id(provider, client_id)
        if provider == "google":
            return replace(self, google_client_id=value)
        return replace(self, microsoft_client_id=value)

    def save(self, path: str | Path | None = None) -> Path:
        config_path = Path(path) if path is not None else default_settings_path()
        config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(config_path.parent, 0o700)
        payload = {
            "google": {"client_id": self.google_client_id},
            "microsoft": {"client_id": self.microsoft_client_id},
        }
        descriptor, temporary = tempfile.mkstemp(
            prefix=".providers-", suffix=".tmp", dir=config_path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, config_path)
            os.chmod(config_path, 0o600)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
        return config_path


_GOOGLE_DESKTOP_CLIENT_ID = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*\.apps\.googleusercontent\.com$"
)


def _validate_public_client_id(provider: str, value: str) -> str:
    candidate = str(value).strip()
    if not candidate or len(candidate) > 512 or not candidate.isprintable() or "\n" in candidate or "\r" in candidate:
        raise ValueError("public client ID must be one printable line of at most 512 characters")
    if provider == "google":
        if not _GOOGLE_DESKTOP_CLIENT_ID.fullmatch(candidate):
            raise ValueError(
                "Google client ID must be a Desktop app ID ending in .apps.googleusercontent.com"
            )
        return candidate
    if provider == "microsoft":
        try:
            normalized = str(uuid.UUID(candidate))
        except (AttributeError, ValueError):
            raise ValueError("Microsoft Application client ID must be a UUID") from None
        if candidate.lower() != normalized:
            raise ValueError("Microsoft Application client ID must be a hyphenated UUID")
        return normalized
    raise ValueError(f"unsupported provider: {provider}")
