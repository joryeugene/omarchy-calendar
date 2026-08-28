# SPDX-License-Identifier: GPL-3.0-or-later
import os
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from omarchy_calendar.cache import CalendarStore
from omarchy_calendar.models import Event, ProviderHealth


def event(
    uid: str = "google:a:c:e",
    *,
    provider: str = "google",
    account: str = "a",
    calendar_id: str = "c",
) -> Event:
    return Event(
        uid=uid,
        provider=provider,
        account_id=account,
        account_label=f"{account}@example.com",
        calendar_id=calendar_id,
        calendar_name="Work",
        calendar_color="#7aa2f7",
        title="Review",
        start="2026-08-25T15:00:00-05:00",
        end="2026-08-25T15:30:00-05:00",
        all_day=False,
        status="confirmed",
        location="",
        description="",
        organizer="",
        meeting_url="",
        provider_url="https://calendar.google.com/calendar/event?eid=e",
        updated="2026-08-25T14:00:00Z",
    )


class CalendarStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "private" / "calendar.db"
        self.store = CalendarStore(self.db)

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_database_and_parent_directory_are_private(self):
        self.assertEqual(stat.S_IMODE(self.db.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.db.parent.stat().st_mode), 0o700)

    def test_replace_window_round_trips_event_and_health(self):
        health = ProviderHealth.ok("google", "a", "2026-08-25T14:01:00Z")
        self.store.replace_window(
            "google",
            "a",
            "2026-08-25T00:00:00Z",
            "2026-08-26T00:00:00Z",
            [event()],
            health,
        )

        view = self.store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")

        self.assertEqual(view["events"][0]["uid"], "google:a:c:e")
        self.assertEqual(view["providers"][0]["last_sync"], "2026-08-25T14:01:00Z")
        self.assertFalse(view["demo"])
        self.assertNotIn("access_token", str(view))

    def test_view_exposes_an_opaque_calendar_catalog_without_persisting_identity_keys(self):
        health = ProviderHealth.ok("google", "private-account", "2026-08-25T14:01:00Z")
        private_event = event(account="private-account", calendar_id="secret-calendar-id")
        self.store.replace_window(
            "google",
            "private-account",
            "2026-08-25T00:00:00Z",
            "2026-08-26T00:00:00Z",
            [private_event],
            health,
        )

        view = self.store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")

        self.assertEqual(len(view["calendars"]), 1)
        selector = view["calendars"][0]["key"]
        self.assertRegex(selector, r"^[0-9a-f]{64}$")
        self.assertEqual(view["events"][0]["calendar_key"], selector)
        self.assertNotIn("private-account", selector)
        self.assertNotIn(private_event.calendar_id, selector)

    def test_calendar_catalog_deduplicates_renamed_calendars_by_stable_identity(self):
        first_window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
        second_window = ("2026-08-27T00:00:00Z", "2026-08-28T00:00:00Z")
        before_rename = event("google:a:c:before")
        after_rename = replace(
            event("google:a:c:after"),
            account_label="new-label@example.com",
            calendar_name="Focused Work",
            calendar_color="#bb9af7",
            start="2026-08-27T15:00:00-05:00",
            end="2026-08-27T15:30:00-05:00",
            updated="2026-08-27T14:00:00Z",
        )
        self.store.replace_window(
            "google", "a", *first_window, [before_rename],
            ProviderHealth.ok("google", "a", first_window[0]),
        )
        self.store.replace_window(
            "google", "a", *second_window, [after_rename],
            ProviderHealth.ok("google", "a", second_window[0]),
        )

        view = self.store.view(first_window[0], second_window[1])

        self.assertEqual(len(view["calendars"]), 1)
        self.assertEqual(view["calendars"][0]["name"], "Focused Work")
        self.assertEqual(view["calendars"][0]["color"], "#bb9af7")
        self.assertEqual(view["calendars"][0]["account_label"], "new-label@example.com")
        self.assertEqual(view["calendars"][0]["event_count"], 2)
        self.assertEqual(
            {item["calendar_key"] for item in view["events"]},
            {view["calendars"][0]["key"]},
        )

    def test_replacing_one_account_preserves_another_account(self):
        window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
        self.store.replace_window("google", "a", *window, [event()], ProviderHealth.ok("google", "a", window[0]))
        other = event("microsoft:b:c:e", provider="microsoft", account="b")
        self.store.replace_window("microsoft", "b", *window, [other], ProviderHealth.ok("microsoft", "b", window[0]))
        replacement = event("google:a:c:new")

        self.store.replace_window("google", "a", *window, [replacement], ProviderHealth.ok("google", "a", window[1]))

        uids = {item["uid"] for item in self.store.view(*window)["events"]}
        self.assertEqual(uids, {"google:a:c:new", "microsoft:b:c:e"})

    def test_clear_demo_removes_only_demo_accounts(self):
        window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
        live = event()
        demo = event("google:demo:c:e", account="demo")
        self.store.replace_window("google", "a", *window, [live], ProviderHealth.ok("google", "a", window[0]))
        self.store.replace_window("google", "demo", *window, [demo], ProviderHealth.ok("google", "demo", window[0], demo=True))

        removed = self.store.clear_demo()

        self.assertEqual(removed, 1)
        self.assertEqual([item["uid"] for item in self.store.view(*window)["events"]], [live.uid])

    def test_account_event_lookup_and_removal_are_scoped(self):
        window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
        google = event()
        outlook = event("microsoft:b:c:e", provider="microsoft", account="b")
        self.store.replace_window("google", "a", *window, [google], ProviderHealth.ok("google", "a", window[0]))
        self.store.replace_window("microsoft", "b", *window, [outlook], ProviderHealth.ok("microsoft", "b", window[0]))

        self.assertEqual(self.store.accounts("google"), [{"provider": "google", "account_id": "a", "connected": True}])
        self.assertEqual(self.store.get_event(google.uid)["provider_url"], google.provider_url)
        self.assertEqual(self.store.remove_account("google", "a"), 1)
        self.assertIsNone(self.store.get_event(google.uid))
        self.assertIsNotNone(self.store.get_event(outlook.uid))

    def test_clear_all_removes_events_and_provider_health(self):
        window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
        self.store.replace_window(
            "google", "a", *window, [event()],
            ProviderHealth.ok("google", "a", window[0]),
        )

        removed = self.store.clear_all()

        self.assertEqual(removed, {"events": 1, "providers": 1})
        self.assertEqual(
            self.store.view(*window),
            {"events": [], "calendars": [], "providers": [], "demo": False},
        )


if __name__ == "__main__":
    unittest.main()
