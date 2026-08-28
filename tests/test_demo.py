# SPDX-License-Identifier: GPL-3.0-or-later
import unittest
from datetime import date

from omarchy_calendar.demo import demo_events


class DemoEventTests(unittest.TestCase):
    def test_demo_covers_providers_links_all_day_overlap_and_recurrence(self):
        events, health = demo_events(date(2026, 8, 26))

        self.assertGreaterEqual(len(events), 22)
        self.assertEqual({event.provider for event in events}, {"google", "microsoft"})
        week_days = {date(2026, 8, 24 + offset).isoformat() for offset in range(7)}
        event_days = {event.start[:10] for event in events}
        self.assertEqual(event_days, week_days)
        self.assertGreaterEqual(sum(event.start[:10] == "2026-08-26" for event in events), 5)
        self.assertGreaterEqual(len({event.start[:10] for event in events if event.all_day}), 2)
        meeting_urls = [event.meeting_url for event in events if event.meeting_url]
        self.assertTrue(all(url.startswith("https://") and ".example.com/" in url for url in meeting_urls))
        self.assertGreaterEqual(len(meeting_urls), 7)
        self.assertGreaterEqual(sum(event.provider == "google" for event in events), 10)
        self.assertGreaterEqual(sum(event.provider == "microsoft" for event in events), 8)
        for title in (
            "Design system freeze", "Product roadmap review", "Dentist appointment",
            "Team lunch", "Deep work", "Trail run", "Weekly reset",
        ):
            self.assertTrue(any(event.title == title for event in events), title)
        self.assertTrue(any("keyboard" in event.description.lower() for event in events))
        self.assertTrue(all(event.provider_url.startswith("https://") for event in events))
        self.assertTrue(any("recurrence" in event.uid for event in events))

        hero = next(event for event in events if event.uid.endswith(":customer-demo"))
        self.assertEqual(hero.title, "Customer demo")
        self.assertEqual(hero.location, "Video call")
        self.assertEqual(hero.meeting_url, "https://video.example.com/customer-demo")
        self.assertIn("press m to join", hero.description.lower())

        self.assertEqual(len(health), 2)
        self.assertTrue(all(item.demo for item in health))
        self.assertTrue(any(item.stale for item in health))

        timed = [event for event in events if not event.all_day]
        overlap = [event for event in timed if event.start < "2026-08-26T11:00:00-05:00" and event.end > "2026-08-26T10:00:00-05:00"]
        self.assertGreaterEqual(len(overlap), 2)

        thursday_events, _ = demo_events(date(2026, 8, 27))
        visible_slots = [(event.title, event.start, event.end) for event in thursday_events]
        self.assertEqual(len(visible_slots), len(set(visible_slots)))


if __name__ == "__main__":
    unittest.main()
