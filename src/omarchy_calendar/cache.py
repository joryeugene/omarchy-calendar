# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Iterable

from .models import Event, ProviderHealth


EVENT_COLUMNS = (
    "uid",
    "provider",
    "account_id",
    "account_label",
    "calendar_id",
    "calendar_name",
    "calendar_color",
    "title",
    "start",
    "end",
    "all_day",
    "status",
    "location",
    "description",
    "organizer",
    "meeting_url",
    "provider_url",
    "updated",
)


class CalendarStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.path.parent, 0o700)
        self.connection = sqlite3.connect(self.path)
        os.chmod(self.path, 0o600)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              uid TEXT PRIMARY KEY,
              provider TEXT NOT NULL,
              account_id TEXT NOT NULL,
              account_label TEXT NOT NULL,
              calendar_id TEXT NOT NULL,
              calendar_name TEXT NOT NULL,
              calendar_color TEXT NOT NULL,
              title TEXT NOT NULL,
              start TEXT NOT NULL,
              end TEXT NOT NULL,
              all_day INTEGER NOT NULL CHECK (all_day IN (0, 1)),
              status TEXT NOT NULL,
              location TEXT NOT NULL,
              description TEXT NOT NULL,
              organizer TEXT NOT NULL,
              meeting_url TEXT NOT NULL,
              provider_url TEXT NOT NULL,
              updated TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_window
              ON events (start, end);
            CREATE INDEX IF NOT EXISTS events_account
              ON events (provider, account_id);
            CREATE TABLE IF NOT EXISTS provider_health (
              provider TEXT NOT NULL,
              account_id TEXT NOT NULL,
              connected INTEGER NOT NULL CHECK (connected IN (0, 1)),
              last_sync TEXT NOT NULL,
              last_error TEXT NOT NULL,
              retry_after TEXT NOT NULL,
              stale INTEGER NOT NULL CHECK (stale IN (0, 1)),
              demo INTEGER NOT NULL CHECK (demo IN (0, 1)),
              skipped INTEGER NOT NULL,
              PRIMARY KEY (provider, account_id)
            );
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "CalendarStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def replace_window(
        self,
        provider: str,
        account_id: str,
        start: str,
        end: str,
        events: Iterable[Event],
        health: ProviderHealth,
    ) -> None:
        if health.provider != provider or health.account_id != account_id:
            raise ValueError("provider health does not match replacement account")
        rows = [self._event_values(event) for event in events]
        with self.connection:
            self.connection.execute(
                """
                DELETE FROM events
                 WHERE provider = ? AND account_id = ?
                   AND julianday(end) > julianday(?)
                   AND julianday(start) < julianday(?)
                """,
                (provider, account_id, start, end),
            )
            self.connection.executemany(
                f"INSERT OR REPLACE INTO events ({', '.join(EVENT_COLUMNS)}) VALUES ({', '.join('?' for _ in EVENT_COLUMNS)})",
                rows,
            )
            self.connection.execute(
                """
                INSERT INTO provider_health
                  (provider, account_id, connected, last_sync, last_error,
                   retry_after, stale, demo, skipped)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, account_id) DO UPDATE SET
                  connected=excluded.connected,
                  last_sync=excluded.last_sync,
                  last_error=excluded.last_error,
                  retry_after=excluded.retry_after,
                  stale=excluded.stale,
                  demo=excluded.demo,
                  skipped=excluded.skipped
                """,
                self._health_values(health),
            )

    def view(self, start: str, end: str) -> dict[str, object]:
        event_rows = self.connection.execute(
            """
            SELECT * FROM events
             WHERE julianday(end) > julianday(?)
               AND julianday(start) < julianday(?)
             ORDER BY julianday(start), all_day DESC, title COLLATE NOCASE
            """,
            (start, end),
        ).fetchall()
        health_rows = self.connection.execute(
            "SELECT * FROM provider_health ORDER BY provider, account_id"
        ).fetchall()
        calendar_rows = self.connection.execute(
            """
            WITH ranked AS (
              SELECT provider, account_id, account_label, calendar_id,
                     calendar_name, calendar_color,
                     COUNT(*) OVER (
                       PARTITION BY provider, account_id, calendar_id
                     ) AS event_count,
                     ROW_NUMBER() OVER (
                       PARTITION BY provider, account_id, calendar_id
                       ORDER BY julianday(updated) DESC, rowid DESC
                     ) AS metadata_rank
                FROM events
            )
            SELECT provider, account_id, account_label, calendar_id,
                   calendar_name, calendar_color, event_count
              FROM ranked
             WHERE metadata_rank = 1
             ORDER BY provider, calendar_name COLLATE NOCASE, account_label COLLATE NOCASE
            """
        ).fetchall()
        providers = [self._public_health(row) for row in health_rows]
        return {
            "events": [self._public_event(row) for row in event_rows],
            "calendars": [self._public_calendar(row) for row in calendar_rows],
            "providers": providers,
            "demo": any(bool(row["demo"]) for row in health_rows),
        }

    def clear_demo(self) -> int:
        accounts = self.connection.execute(
            "SELECT provider, account_id FROM provider_health WHERE demo = 1"
        ).fetchall()
        with self.connection:
            for row in accounts:
                self.connection.execute(
                    "DELETE FROM events WHERE provider = ? AND account_id = ?",
                    (row["provider"], row["account_id"]),
                )
            self.connection.execute("DELETE FROM provider_health WHERE demo = 1")
        return len(accounts)

    def clear_all(self) -> dict[str, int]:
        events = int(self.connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
        providers = int(self.connection.execute("SELECT COUNT(*) FROM provider_health").fetchone()[0])
        with self.connection:
            self.connection.execute("DELETE FROM events")
            self.connection.execute("DELETE FROM provider_health")
        return {"events": events, "providers": providers}

    def accounts(self, provider: str | None = None, *, include_demo: bool = False) -> list[dict[str, object]]:
        conditions: list[str] = []
        values: list[object] = []
        if provider is not None:
            conditions.append("provider = ?")
            values.append(provider)
        if not include_demo:
            conditions.append("demo = 0")
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        rows = self.connection.execute(
            "SELECT provider, account_id, connected FROM provider_health" + where + " ORDER BY provider, account_id",
            values,
        ).fetchall()
        return [
            {
                "provider": row["provider"],
                "account_id": row["account_id"],
                "connected": bool(row["connected"]),
            }
            for row in rows
        ]

    def health_records(self) -> list[dict[str, object]]:
        rows = self.connection.execute(
            "SELECT * FROM provider_health ORDER BY provider, account_id"
        ).fetchall()
        return [self._public_health(row) for row in rows]

    def health(self, provider: str, account_id: str) -> ProviderHealth | None:
        row = self.connection.execute(
            "SELECT * FROM provider_health WHERE provider = ? AND account_id = ?",
            (provider, account_id),
        ).fetchone()
        if row is None:
            return None
        return ProviderHealth(
            provider=row["provider"],
            account_id=row["account_id"],
            connected=bool(row["connected"]),
            last_sync=row["last_sync"],
            last_error=row["last_error"],
            retry_after=row["retry_after"],
            stale=bool(row["stale"]),
            demo=bool(row["demo"]),
            skipped=row["skipped"],
        )

    def set_health(self, health: ProviderHealth) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO provider_health
                  (provider, account_id, connected, last_sync, last_error,
                   retry_after, stale, demo, skipped)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(provider, account_id) DO UPDATE SET
                  connected=excluded.connected,
                  last_sync=excluded.last_sync,
                  last_error=excluded.last_error,
                  retry_after=excluded.retry_after,
                  stale=excluded.stale,
                  demo=excluded.demo,
                  skipped=excluded.skipped
                """,
                self._health_values(health),
            )

    def get_event(self, uid: str) -> dict[str, object] | None:
        row = self.connection.execute("SELECT * FROM events WHERE uid = ?", (uid,)).fetchone()
        return self._public_event(row) if row is not None else None

    def remove_account(self, provider: str, account_id: str) -> int:
        with self.connection:
            self.connection.execute(
                "DELETE FROM events WHERE provider = ? AND account_id = ?",
                (provider, account_id),
            )
            cursor = self.connection.execute(
                "DELETE FROM provider_health WHERE provider = ? AND account_id = ?",
                (provider, account_id),
            )
        return cursor.rowcount

    @staticmethod
    def _event_values(event: Event) -> tuple[object, ...]:
        data = event.to_dict()
        data["all_day"] = int(event.all_day)
        return tuple(data[column] for column in EVENT_COLUMNS)

    @staticmethod
    def _health_values(health: ProviderHealth) -> tuple[object, ...]:
        return (
            health.provider,
            health.account_id,
            int(health.connected),
            health.last_sync,
            health.last_error,
            health.retry_after,
            int(health.stale),
            int(health.demo),
            health.skipped,
        )

    @staticmethod
    def _public_event(row: sqlite3.Row) -> dict[str, object]:
        result = {
            column: bool(row[column]) if column == "all_day" else row[column]
            for column in EVENT_COLUMNS
        }
        result["calendar_key"] = CalendarStore._calendar_key(row)
        return result

    @staticmethod
    def _public_calendar(row: sqlite3.Row) -> dict[str, object]:
        return {
            "key": CalendarStore._calendar_key(row),
            "provider": row["provider"],
            "account_label": row["account_label"],
            "name": row["calendar_name"],
            "color": row["calendar_color"],
            "event_count": int(row["event_count"]),
        }

    @staticmethod
    def _calendar_key(row: sqlite3.Row) -> str:
        identity = "\0".join((row["provider"], row["account_id"], row["calendar_id"]))
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()

    @staticmethod
    def _public_health(row: sqlite3.Row) -> dict[str, object]:
        return {
            "provider": row["provider"],
            "account_id": row["account_id"],
            "connected": bool(row["connected"]),
            "last_sync": row["last_sync"],
            "last_error": row["last_error"],
            "retry_after": row["retry_after"],
            "stale": bool(row["stale"]),
            "demo": bool(row["demo"]),
            "skipped": row["skipped"],
        }
