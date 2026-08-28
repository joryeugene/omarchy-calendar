# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .models import Event, ProviderHealth


ZONE = ZoneInfo("America/Chicago")


def _iso(day: date, hour: int, minute: int = 0) -> str:
    return datetime.combine(day, time(hour, minute), ZONE).isoformat()


def _event(
    *,
    uid: str,
    provider: str,
    title: str,
    day: date,
    start: tuple[int, int],
    end: tuple[int, int],
    meeting_url: str = "",
    description: str = "",
    location: str = "",
    all_day: bool = False,
) -> Event:
    account = f"demo-{provider}"
    provider_url = (
        f"https://calendar.google.com/calendar/event?eid={uid}"
        if provider == "google"
        else f"https://outlook.live.com/calendar/item/{uid}"
    )
    return Event(
        uid=f"{provider}:{account}:primary:{uid}",
        provider=provider,
        account_id=account,
        account_label=f"Demo {provider.title()}",
        calendar_id="primary",
        calendar_name="Work" if provider == "google" else "Personal",
        calendar_color="#7aa2f7" if provider == "google" else "#bb9af7",
        title=title,
        start=(datetime.combine(day, time.min, ZONE).isoformat() if all_day else _iso(day, *start)),
        end=(datetime.combine(day + timedelta(days=1), time.min, ZONE).isoformat() if all_day else _iso(day, *end)),
        all_day=all_day,
        status="confirmed",
        location=location,
        description=description,
        organizer="Demo organizer",
        meeting_url=meeting_url,
        provider_url=provider_url,
        updated=_iso(day, 7),
    )


def demo_events(day: date | None = None) -> tuple[list[Event], list[ProviderHealth]]:
    day = day or datetime.now(ZONE).date()
    monday = day - timedelta(days=day.weekday())
    second_standup_day = monday + timedelta(days=3)
    if second_standup_day == day:
        second_standup_day = monday + timedelta(days=2)
    events = [
        _event(uid="design-system-freeze", provider="google", title="Design system freeze", day=monday,
               start=(0, 0), end=(0, 0), all_day=True),
        _event(uid="weekly-planning", provider="google", title="Weekly planning", day=monday,
               start=(9, 0), end=(10, 0),
               description="Set the release priorities and protect the week's focus blocks."),
        _event(uid="focus-sprint", provider="microsoft", title="Focus sprint", day=monday,
               start=(10, 30), end=(12, 0)),
        _event(uid="product-roadmap", provider="google", title="Product roadmap review", day=monday,
               start=(15, 30), end=(16, 15), meeting_url="https://meet.example.com/product-roadmap"),
        _event(uid="portfolio-review", provider="google", title="Portfolio review", day=monday + timedelta(days=1),
               start=(9, 30), end=(10, 15), meeting_url="https://meet.example.com/portfolio-review"),
        _event(uid="candidate-interview", provider="microsoft", title="Candidate interview", day=monday + timedelta(days=1),
               start=(11, 0), end=(12, 0), meeting_url="https://teams.example.com/candidate-interview"),
        _event(uid="customer-research", provider="google", title="Customer research", day=monday + timedelta(days=1),
               start=(14, 0), end=(15, 0), meeting_url="https://meet.example.com/customer-research"),
        _event(uid="dentist", provider="microsoft", title="Dentist appointment", day=monday + timedelta(days=1),
               start=(16, 30), end=(17, 15), location="Lakeside Dental"),
        _event(uid="release-candidate-day", provider="google", title="Release candidate day", day=day,
               start=(0, 0), end=(0, 0), all_day=True),
        _event(uid="recurrence-standup-wed", provider="google", title="Daily standup", day=day,
               start=(9, 0), end=(9, 25), meeting_url="https://meet.example.com/daily-standup"),
        _event(uid="design-review", provider="google", title="Calendar design review", day=day,
               start=(10, 0), end=(11, 0),
               description="Review the Today focus view and keyboard navigation before release."),
        _event(uid="mentor-call", provider="microsoft", title="Mentor call", day=day,
               start=(10, 30), end=(11, 15), meeting_url="https://teams.example.com/mentor-call"),
        _event(uid="customer-demo", provider="google", title="Customer demo", day=day,
               start=(13, 30), end=(14, 15), meeting_url="https://video.example.com/customer-demo",
               location="Video call",
               description="Show the team how Today turns a busy schedule into one clear next action. Press m to join, then review the keyboard flow and private local sync."),
        _event(uid="recurrence-standup-other", provider="google", title="Daily standup", day=second_standup_day,
               start=(9, 0), end=(9, 25), meeting_url="https://meet.example.com/daily-standup"),
        _event(uid="team-lunch", provider="microsoft", title="Team lunch", day=monday + timedelta(days=3),
               start=(12, 0), end=(13, 0), location="North Loop"),
        _event(uid="release-notes", provider="microsoft", title="Write release notes", day=monday + timedelta(days=3),
               start=(15, 0), end=(16, 0)),
        _event(uid="release-deploy", provider="google", title="Release deploy", day=monday + timedelta(days=3),
               start=(16, 30), end=(17, 30), meeting_url="https://meet.example.com/release-deploy"),
        _event(uid="budget-review", provider="microsoft", title="Budget review", day=monday + timedelta(days=4),
               start=(9, 30), end=(10, 15), meeting_url="https://teams.example.com/budget-review"),
        _event(uid="launch-readiness", provider="google", title="Launch readiness", day=monday + timedelta(days=4),
               start=(11, 0), end=(12, 0), meeting_url="https://meet.example.com/launch-readiness"),
        _event(uid="deep-work", provider="google", title="Deep work", day=monday + timedelta(days=4),
               start=(13, 30), end=(15, 30), description="Protected build time with notifications off."),
        _event(uid="community-day", provider="google", title="Community day", day=monday + timedelta(days=5),
               start=(0, 0), end=(0, 0), all_day=True),
        _event(uid="trail-run", provider="microsoft", title="Trail run", day=monday + timedelta(days=5),
               start=(8, 0), end=(9, 0), location="River trail"),
        _event(uid="farmers-market", provider="microsoft", title="Farmers market", day=monday + timedelta(days=5),
               start=(10, 0), end=(11, 30)),
        _event(uid="travel-day", provider="microsoft", title="Travel day", day=monday + timedelta(days=6),
               start=(0, 0), end=(0, 0), all_day=True),
        _event(uid="weekly-reset", provider="google", title="Weekly reset", day=monday + timedelta(days=6),
               start=(17, 0), end=(18, 0), description="Review commitments and prepare Monday's first focus block."),
    ]
    now = datetime.now(ZONE).isoformat()
    google = ProviderHealth.ok("google", "demo-google", now, demo=True)
    microsoft = replace(
        ProviderHealth.ok("microsoft", "demo-microsoft", now, demo=True),
        stale=True,
        last_error="Demo provider is intentionally stale",
    )
    return events, [google, microsoft]
