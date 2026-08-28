# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

from ..models import Account, Event
from ..normalize import extract_meeting_url, is_safe_https_url, plain_text


GRAPH = "https://graph.microsoft.com/v1.0"

_COLORS = {
    "auto": "#7aa2f7",
    "lightBlue": "#7dcfff",
    "lightGreen": "#9ece6a",
    "lightOrange": "#ff9e64",
    "lightGray": "#7982a9",
    "lightYellow": "#e0af68",
    "lightTeal": "#73daca",
    "lightPink": "#f7768e",
    "lightBrown": "#c0a36e",
    "lightRed": "#f7768e",
    "maxColor": "#bb9af7",
    "lightPurple": "#bb9af7",
    "darkBlue": "#2ac3de",
    "darkGreen": "#73daca",
    "darkOrange": "#ff9e64",
    "darkGray": "#565f89",
    "darkYellow": "#e0af68",
    "darkTeal": "#41a6b5",
    "darkPink": "#db4b4b",
    "darkBrown": "#9d7c61",
    "darkRed": "#db4b4b",
    "darkPurple": "#9d7cd8",
}

_WINDOWS_ZONES = {
    "UTC": timezone.utc,
    "Central Standard Time": ZoneInfo("America/Chicago"),
    "Eastern Standard Time": ZoneInfo("America/New_York"),
    "Mountain Standard Time": ZoneInfo("America/Denver"),
    "Pacific Standard Time": ZoneInfo("America/Los_Angeles"),
}


def _graph_time(value: dict[str, Any]) -> str:
    raw = str(value.get("dateTime") or "")
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        zone = _WINDOWS_ZONES.get(str(value.get("timeZone") or "UTC"), timezone.utc)
        parsed = parsed.replace(tzinfo=zone)
    return parsed.isoformat()


def _meeting_url(raw: dict[str, Any]) -> str:
    direct = str((raw.get("onlineMeeting") or {}).get("joinUrl") or "")
    if is_safe_https_url(direct):
        return direct
    legacy = str(raw.get("onlineMeetingUrl") or "")
    if is_safe_https_url(legacy):
        return legacy
    location = str((raw.get("location") or {}).get("displayName") or "")
    return extract_meeting_url(location, str(raw.get("bodyPreview") or ""))


def normalize_microsoft_event(
    raw: dict[str, Any],
    account: Account,
    calendar: dict[str, Any],
) -> Event | None:
    if raw.get("isCancelled") is True:
        return None
    calendar_id = str(calendar.get("id") or "")
    event_id = str(raw.get("id") or "")
    organizer = (raw.get("organizer") or {}).get("emailAddress") or {}
    organizer_text = str(organizer.get("name") or organizer.get("address") or "")
    location = str((raw.get("location") or {}).get("displayName") or "")
    provider_url = str(raw.get("webLink") or "")
    if not is_safe_https_url(provider_url):
        provider_url = ""
    return Event(
        uid=f"microsoft:{account.account_id}:{calendar_id}:{event_id}",
        provider="microsoft",
        account_id=account.account_id,
        account_label=account.label,
        calendar_id=calendar_id,
        calendar_name=str(calendar.get("name") or "Outlook Calendar"),
        calendar_color=_COLORS.get(str(calendar.get("color") or "auto"), "#bb9af7"),
        title=str(raw.get("subject") or "Untitled event"),
        start=_graph_time(raw.get("start", {})),
        end=_graph_time(raw.get("end", {})),
        all_day=bool(raw.get("isAllDay")),
        status="confirmed",
        location=plain_text(location, 500),
        description=plain_text(str(raw.get("bodyPreview") or "")),
        organizer=organizer_text,
        meeting_url=_meeting_url(raw),
        provider_url=provider_url,
        updated=str(raw.get("lastModifiedDateTime") or ""),
    )


class MicrosoftProvider:
    def __init__(self, http: Any):
        self.http = http

    def fetch_window(self, token: str, start: str, end: str) -> tuple[Account, list[Event]]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Prefer": 'outlook.timezone="UTC"',
        }
        identity = self.http.get_json(
            f"{GRAPH}/me?{urlencode({'$select': 'id,displayName,mail,userPrincipalName'})}",
            headers=headers,
        )
        account = Account(
            provider="microsoft",
            account_id=str(identity["id"]),
            label=str(identity.get("mail") or identity.get("userPrincipalName") or identity.get("displayName") or "Outlook"),
        )
        calendars = self._calendars(headers)
        events: list[Event] = []
        for calendar in calendars:
            events.extend(self._events(calendar, account, headers, start, end))
        return account, events

    def _calendars(self, headers: dict[str, str]) -> list[dict[str, Any]]:
        url = f"{GRAPH}/me/calendars?{urlencode({'$select': 'id,name,color'})}"
        items: list[dict[str, Any]] = []
        while url:
            payload = self.http.get_json(url, headers=headers)
            items.extend(payload.get("value", []))
            url = str(payload.get("@odata.nextLink") or "")
        return items

    def _events(
        self,
        calendar: dict[str, Any],
        account: Account,
        headers: dict[str, str],
        start: str,
        end: str,
    ) -> list[Event]:
        calendar_id = quote(str(calendar["id"]), safe="")
        fields = (
            "id,subject,start,end,isAllDay,isCancelled,bodyPreview,location,"
            "organizer,onlineMeeting,onlineMeetingUrl,webLink,showAs,"
            "lastModifiedDateTime,type,seriesMasterId"
        )
        query = urlencode({
            "startDateTime": start,
            "endDateTime": end,
            "$select": fields,
            "$top": "1000",
        })
        url = f"{GRAPH}/me/calendars/{calendar_id}/calendarView?{query}"
        events: list[Event] = []
        while url:
            payload = self.http.get_json(url, headers=headers)
            for raw in payload.get("value", []):
                event = normalize_microsoft_event(raw, account, calendar)
                if event is not None:
                    events.append(event)
            url = str(payload.get("@odata.nextLink") or "")
        return events
