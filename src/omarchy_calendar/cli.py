# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

from .auth_service import Authenticator
from .cache import CalendarStore
from .demo import ZONE, demo_events
from .keyring import KeyringError, SecretServiceStore, redact
from .normalize import is_safe_https_url
from .settings import ProviderSettings
from .sync import SyncEngine


def state_path() -> Path:
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "omarchy-calendar" / "calendar.db"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="calendarctl", description="Read-only Omarchy calendar helper")
    commands = root.add_subparsers(dest="command", required=True)
    auth = commands.add_parser("auth")
    auth.add_argument("provider", choices=("google", "microsoft"))
    sync = commands.add_parser("sync")
    sync.add_argument("--provider", choices=("google", "microsoft"))
    view = commands.add_parser("view")
    view.add_argument("--from", dest="start", required=True)
    view.add_argument("--to", dest="end", required=True)
    commands.add_parser("status")
    commands.add_parser("setup-status")
    configure = commands.add_parser("configure-client")
    configure.add_argument("provider", choices=("microsoft",))
    configure.add_argument("client_id")
    import_google = commands.add_parser("import-google-desktop-app")
    import_google.add_argument("credentials_json")
    disconnect = commands.add_parser("disconnect")
    disconnect.add_argument("provider", choices=("google", "microsoft"))
    disconnect.add_argument("--account")
    commands.add_parser("reset-local-data")
    for name in ("open-meeting", "open-source"):
        action = commands.add_parser(name)
        action.add_argument("uid")
    demo = commands.add_parser("demo")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    seed = demo_commands.add_parser("seed")
    seed.add_argument("--date")
    demo_commands.add_parser("clear")
    return root


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def seed_demo(store: CalendarStore, selected_day: date) -> dict[str, object]:
    events, health = demo_events(selected_day)
    grouped: dict[tuple[str, str], list] = defaultdict(list)
    for event in events:
        grouped[(event.provider, event.account_id)].append(event)
    start = datetime.combine(selected_day - timedelta(days=1), time.min, ZONE).isoformat()
    end = datetime.combine(selected_day + timedelta(days=3), time.min, ZONE).isoformat()
    health_by_account = {(item.provider, item.account_id): item for item in health}
    for key, account_events in grouped.items():
        store.replace_window(*key, start, end, account_events, health_by_account[key])
    return {"seeded": len(events), "accounts": len(grouped), "date": selected_day.isoformat(), "demo": True}


def open_event_url(
    store: CalendarStore,
    uid: str,
    field: str,
    *,
    command: str | None = None,
    runner=subprocess.run,
) -> int:
    event = store.get_event(uid)
    if event is None:
        print("Event is not available in the local cache", file=sys.stderr)
        return 4
    url = str(event.get(field) or "")
    if not is_safe_https_url(url):
        print("This event does not provide that action", file=sys.stderr)
        return 4
    executable = command or os.environ.get("OMARCHY_CALENDAR_OPEN_COMMAND", "xdg-open")
    runner([executable, url], check=False)
    return 0


def setup_status(
    store: CalendarStore,
    settings: ProviderSettings,
    keyring: SecretServiceStore | None = None,
) -> dict[str, object]:
    health = store.health_records()
    providers = []
    for provider, label in (("google", "Google"), ("microsoft", "Outlook")):
        real = [item for item in health if item["provider"] == provider and not item["demo"]]
        connected = [item for item in real if item["connected"]]
        configured = bool(settings.client_id(provider))
        if provider == "google" and configured:
            configured = bool(
                settings.google_app_credential(keyring or SecretServiceStore())
            )
        providers.append({
            "provider": provider,
            "label": label,
            "client_configured": configured,
            "registration_source": settings.registration_source(provider),
            "connected": bool(connected),
            "accounts": len(real),
            "stale": any(bool(item["stale"]) for item in real),
            "last_sync": str(real[0]["last_sync"]) if real else "",
            "last_error": next((str(item["last_error"]) for item in real if item["last_error"]), ""),
        })
    return {
        "providers": providers,
        "demo": any(bool(item["demo"]) for item in health),
    }


def disconnect_provider(
    store: CalendarStore,
    keyring: SecretServiceStore,
    provider: str,
    account_id: str | None = None,
) -> dict[str, object]:
    accounts = store.accounts(provider)
    if account_id:
        accounts = [item for item in accounts if item["account_id"] == account_id]
    removed = 0
    for account in accounts:
        account = str(account["account_id"])
        keyring.clear(provider, account)
        removed += store.remove_account(provider, account)
    return {"provider": provider, "disconnected": removed}


def reset_local_data(
    store: CalendarStore,
    keyring: SecretServiceStore,
    settings_path: str | Path | None = None,
) -> dict[str, object]:
    keyring.clear_all()
    removed = store.clear_all()
    removed["provider_overrides"] = int(ProviderSettings.clear(settings_path))
    return removed


def import_google_desktop_app(
    source: str | Path,
    keyring: SecretServiceStore,
    settings_path: str | Path | None = None,
) -> dict[str, object]:
    source_text = os.fspath(source)
    parsed = urlparse(source_text)
    if parsed.scheme:
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            raise ValueError("Google Desktop credentials must be a local file")
        if parsed.query or parsed.fragment:
            raise ValueError("Google Desktop credentials must be a plain local file")
        source = Path(unquote(parsed.path))
    source = Path(source)
    if not source.is_absolute():
        raise ValueError("Google Desktop credentials must be an absolute local file")
    try:
        descriptor = os.open(source, os.O_RDONLY | os.O_NONBLOCK)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError("Google Desktop credentials must be a regular file")
            if metadata.st_size > 65536:
                raise ValueError("Google Desktop credentials file is too large")
            raw = os.read(descriptor, 65537)
        finally:
            os.close(descriptor)
        if len(raw) > 65536:
            raise ValueError("Google Desktop credentials file is too large")
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Google Desktop credentials file is not valid JSON") from error
    installed = payload.get("installed") if isinstance(payload, dict) else None
    if not isinstance(installed, dict):
        raise ValueError("Google credentials must be for a Desktop app")
    client_id = str(installed.get("client_id") or "").strip()
    credential = str(installed.get("client_secret") or "").strip()
    settings = ProviderSettings.load(settings_path).with_client_id("google", client_id)
    keyring.put_app_credential("google", credential)
    settings.save(settings_path)
    return {"provider": "google", "configured": True}


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        with CalendarStore(state_path()) as store:
            if arguments.command == "demo":
                if arguments.demo_command == "seed":
                    selected = date.fromisoformat(arguments.date) if arguments.date else datetime.now(ZONE).date()
                    emit(seed_demo(store, selected))
                else:
                    emit({"cleared_accounts": store.clear_demo(), "demo": False})
                return 0
            if arguments.command == "view":
                emit(store.view(arguments.start, arguments.end))
                return 0
            if arguments.command == "status":
                emit({"providers": store.health_records(), "database": str(store.path)})
                return 0
            if arguments.command == "setup-status":
                emit(setup_status(store, ProviderSettings.load()))
                return 0
            if arguments.command == "configure-client":
                ProviderSettings.load().with_client_id(arguments.provider, arguments.client_id).save()
                emit({"provider": arguments.provider, "configured": True})
                return 0
            if arguments.command == "import-google-desktop-app":
                emit(import_google_desktop_app(arguments.credentials_json, SecretServiceStore()))
                return 0
            if arguments.command == "auth":
                settings = ProviderSettings.load()
                if not settings.client_id(arguments.provider):
                    print(f"{arguments.provider} public client ID is not configured", file=sys.stderr)
                    return 3
                emit(Authenticator(store, settings=settings).authenticate(arguments.provider))
                return 0
            if arguments.command == "sync":
                emit(SyncEngine(store).sync(arguments.provider))
                return 0
            if arguments.command == "disconnect":
                emit(disconnect_provider(
                    store,
                    SecretServiceStore(),
                    arguments.provider,
                    arguments.account,
                ))
                return 0
            if arguments.command == "reset-local-data":
                emit(reset_local_data(store, SecretServiceStore()))
                return 0
            if arguments.command == "open-meeting":
                return open_event_url(store, arguments.uid, "meeting_url")
            if arguments.command == "open-source":
                return open_event_url(store, arguments.uid, "provider_url")
    except (ValueError, RuntimeError, KeyringError) as error:
        print(redact(str(error)), file=sys.stderr)
        return 2
    return 2
