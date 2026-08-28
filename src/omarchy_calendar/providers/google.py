# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import date, datetime, time
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models import Account, Event
from ..normalize import extract_meeting_url, is_recognized_meeting_url, is_safe_https_url, plain_text


GOOGLE_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_USERINFO = "https://openidconnect.googleapis.com/v1/userinfo"


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _google_time(value: dict[str, Any], calendar: dict[str, Any]) -> tuple[str, bool]:
    if value.get("dateTime"):
        parsed = datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
        return parsed.isoformat(), False
    day = date.fromisoformat(str(value["date"]))
    zone = _zone(str(value.get("timeZone") or calendar.get("timeZone") or "UTC"))
    return datetime.combine(day, time.min, zone).isoformat(), True


def _conference_url(raw: dict[str, Any]) -> str:
    hangout = str(raw.get("hangoutLink") or "")
    if is_recognized_meeting_url(hangout):
        return hangout
    for entry in raw.get("conferenceData", {}).get("entryPoints", []):
        uri = str(entry.get("uri") or "")
        if entry.get("entryPointType") == "video" and is_safe_https_url(uri):
            return uri
    return extract_meeting_url(str(raw.get("location") or ""), str(raw.get("description") or ""))


def normalize_google_event(
    raw: dict[str, Any],
    account: Account,
    calendar: dict[str, Any],
) -> Event | None:
    if raw.get("status") == "cancelled":
        return None
    start, all_day = _google_time(raw.get("start", {}), calendar)
    end, _ = _google_time(raw.get("end", {}), calendar)
    event_id = str(raw.get("id") or "")
    calendar_id = str(calendar.get("id") or "")
    organizer = raw.get("organizer", {})
    organizer_text = str(organizer.get("displayName") or organizer.get("email") or "")
    provider_url = str(raw.get("htmlLink") or "")
    if not is_safe_https_url(provider_url):
        provider_url = ""
    return Event(
        uid=f"google:{account.account_id}:{calendar_id}:{event_id}",
        provider="google",
        account_id=account.account_id,
        account_label=account.label,
        calendar_id=calendar_id,
        calendar_name=str(calendar.get("summary") or "Google Calendar"),
        calendar_color=str(calendar.get("backgroundColor") or "#7aa2f7"),
        title=str(raw.get("summary") or "Untitled event"),
        start=start,
        end=end,
        all_day=all_day,
        status=str(raw.get("status") or "confirmed"),
        location=plain_text(str(raw.get("location") or ""), 500),
        description=plain_text(str(raw.get("description") or "")),
        organizer=organizer_text,
        meeting_url=_conference_url(raw),
        provider_url=provider_url,
        updated=str(raw.get("updated") or ""),
    )


class GoogleProvider:
    def __init__(self, http: Any):
        self.http = http

    def fetch_window(self, token: str, start: str, end: str) -> tuple[Account, list[Event]]:
        headers = {"Authorization": f"Bearer {token}"}
        identity = self.http.get_json(GOOGLE_USERINFO, headers=headers)
        account = Account(
            provider="google",
            account_id=str(identity["sub"]),
            label=str(identity.get("email") or "Google"),
        )
        calendars = self._calendar_list(headers)
        events: list[Event] = []
        for calendar in calendars:
            if calendar.get("selected") is False or calendar.get("deleted") is True:
                continue
            events.extend(self._events(calendar, account, headers, start, end))
        return account, events

    def _calendar_list(self, headers: dict[str, str]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        page_token = ""
        while True:
            query = {"maxResults": "250"}
            if page_token:
                query["pageToken"] = page_token
            payload = self.http.get_json(
                f"{GOOGLE_API}/users/me/calendarList?{urlencode(query)}",
                headers=headers,
            )
            items.extend(payload.get("items", []))
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                return items

    def _events(
        self,
        calendar: dict[str, Any],
        account: Account,
        headers: dict[str, str],
        start: str,
        end: str,
    ) -> list[Event]:
        events: list[Event] = []
        page_token = ""
        while True:
            query = {
                "timeMin": start,
                "timeMax": end,
                "singleEvents": "true",
                "showDeleted": "false",
                "maxResults": "2500",
            }
            if page_token:
                query["pageToken"] = page_token
            calendar_id = quote(str(calendar["id"]), safe="")
            payload = self.http.get_json(
                f"{GOOGLE_API}/calendars/{calendar_id}/events?{urlencode(query)}",
                headers=headers,
            )
            for raw in payload.get("items", []):
                event = normalize_google_event(raw, account, calendar)
                if event is not None:
                    events.append(event)
            page_token = str(payload.get("nextPageToken") or "")
            if not page_token:
                return events
