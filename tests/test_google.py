# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from omarchy_calendar.models import Account
from omarchy_calendar.providers.google import GoogleProvider, normalize_google_event


FIXTURES = Path(__file__).parents[1] / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


ACCOUNT = Account("google", "google-subject", "person@example.com")
CALENDAR = {
    "id": "primary@example.com",
    "summary": "Work",
    "backgroundColor": "#7aa2f7",
    "timeZone": "America/Chicago",
}


class FakeHttp:
    def __init__(self):
        self.urls = []

    def get_json(self, url, headers=None):
        self.urls.append(url)
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if parsed.netloc == "openidconnect.googleapis.com":
            return {"sub": "google-subject", "email": "person@example.com"}
        if parsed.path.endswith("/users/me/calendarList"):
            if query.get("pageToken") == ["cal-page-2"]:
                return {"items": [{
                    "id": "personal@example.com", "summary": "Personal",
                    "backgroundColor": "#bb9af7", "timeZone": "America/Chicago",
                    "selected": True
                }]}
            return load_fixture("google-calendar-list.json")
        if "/events" in parsed.path:
            if query.get("pageToken") == ["event-page-2"]:
                return {"items": []}
            return load_fixture("google-events.json")
        raise AssertionError(f"unexpected URL: {url}")


class GoogleProviderTests(unittest.TestCase):
    def test_event_keeps_meeting_provider_link_and_plain_description(self):
        raw = load_fixture("google-events.json")["items"][0]
        result = normalize_google_event(raw, ACCOUNT, CALENDAR)

        self.assertEqual(result.meeting_url, "https://meet.google.com/abc-defg-hij")
        self.assertEqual(result.provider_url, raw["htmlLink"])
        self.assertEqual(result.description, "Review the selected direction.")
        self.assertEqual(result.uid, "google:google-subject:primary@example.com:event-1")

    def test_all_day_event_uses_calendar_timezone_and_cancelled_is_skipped(self):
        items = load_fixture("google-events.json")["items"]
        all_day = normalize_google_event(items[1], ACCOUNT, CALENDAR)
        cancelled = normalize_google_event(items[2], ACCOUNT, CALENDAR)

        self.assertTrue(all_day.all_day)
        self.assertEqual(all_day.start, "2026-08-25T00:00:00-05:00")
        self.assertEqual(all_day.end, "2026-08-26T00:00:00-05:00")
        self.assertIsNone(cancelled)

    def test_provider_follows_calendar_and_event_pagination(self):
        http = FakeHttp()
        provider = GoogleProvider(http)

        account, events = provider.fetch_window(
            "access-token", "2026-08-25T00:00:00Z", "2026-08-27T00:00:00Z"
        )

        self.assertEqual(account, ACCOUNT)
        self.assertEqual(len(events), 4)
        self.assertTrue(any("pageToken=cal-page-2" in url for url in http.urls))
        self.assertGreaterEqual(sum("pageToken=event-page-2" in url for url in http.urls), 2)
        event_urls = [url for url in http.urls if "/events" in url]
        self.assertTrue(all("singleEvents=true" in url for url in event_urls))
        self.assertTrue(all("showDeleted=false" in url for url in event_urls))


if __name__ == "__main__":
    unittest.main()
