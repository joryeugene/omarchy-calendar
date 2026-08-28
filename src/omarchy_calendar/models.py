# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class Event:
    uid: str
    provider: str
    account_id: str
    account_label: str
    calendar_id: str
    calendar_name: str
    calendar_color: str
    title: str
    start: str
    end: str
    all_day: bool
    status: str
    location: str
    description: str
    organizer: str
    meeting_url: str
    provider_url: str
    updated: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider: str
    account_id: str
    connected: bool
    last_sync: str
    last_error: str = ""
    retry_after: str = ""
    stale: bool = False
    demo: bool = False
    skipped: int = 0

    @classmethod
    def ok(
        cls,
        provider: str,
        account_id: str,
        last_sync: str,
        *,
        demo: bool = False,
    ) -> "ProviderHealth":
        return cls(
            provider=provider,
            account_id=account_id,
            connected=True,
            last_sync=last_sync,
            demo=demo,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class Account:
    provider: str
    account_id: str
    label: str
