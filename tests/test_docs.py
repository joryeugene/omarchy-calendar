# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
GUIDE_DATA = ROOT / "docs" / "shortcuts.json"


class DocumentationTests(unittest.TestCase):
    def test_public_preview_docs_put_bring_your_own_oauth_before_installation(self):
        install_command = (
            "omarchy plugin add https://github.com/joryeugene/omarchy-calendar.git --enable"
        )
        for path, after in (
            (ROOT / "README.md", "## Connect Google and Outlook"),
            (ROOT / "docs" / "INSTALL.md", "## Provider setup"),
        ):
            document = path.read_text(encoding="utf-8")
            prerequisite = document.index("## Bring your own OAuth registration")
            self.assertLess(prerequisite, document.index("## Install"))
            self.assertLess(prerequisite, document.index(after))
            self.assertIn(install_command, document)
            self.assertIn("Google Desktop OAuth app", document)
            self.assertIn("Microsoft public desktop app", document)
            self.assertIn("not one-click or seamless", document)

    def test_install_guide_covers_security_setup_and_operations(self):
        guide = (ROOT / "docs/INSTALL.md").read_text(encoding="utf-8")
        for required in (
            "calendar.events.readonly",
            "calendar.calendarlist.readonly",
            "Calendars.Read",
            '"$calendarctl" demo seed',
            '"$calendarctl" auth google',
            '"$calendarctl" auth microsoft',
            '"$calendarctl" import-google-desktop-app',
            '"$calendarctl" disconnect',
            '"$calendarctl" reset-local-data',
            '"$calendarctl" status',
            "~/.local/state/omarchy-calendar/calendar.db",
            "system keyring",
            "omarchy plugin add",
            "io.github.joryeugene.omarchy-calendar",
            "Super+Shift+C",
        ):
            self.assertIn(required, guide)
        for retired in (
            "scripts/install",
            "scripts/rollback",
            "omarchy-calendar-sync.timer",
            "jep.calendar",
            "configure-client-secret",
        ):
            self.assertNotIn(retired, guide)

    def test_readme_has_release_order_privacy_and_configuration_reference(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        headings = (
            "## Install",
            "## Connect Google and Outlook",
            "## Keyboard map",
            "## Today focus and meeting actions",
            "## Settings and themes",
            "## Configuration reference",
            "## Storage and privacy",
            "## Troubleshooting",
            "## Uninstall and delete local data",
        )
        positions = [readme.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        week_image = "screenshots/flight-deck-calendar-week.png"
        today_image = "screenshots/flight-deck-calendar-today.png"
        self.assertLess(readme.index(week_image), readme.index("## Bring your own OAuth"))
        self.assertGreater(readme.index(today_image), readme.index("## Keyboard map"))
        self.assertLess(readme.index(today_image), readme.index("## Settings and themes"))
        self.assertIn("No hosted backend", readme)
        self.assertIn("public preview", readme)
        self.assertNotIn("private local installation", readme)
        self.assertNotIn("rollback flow", readme)
        for key in (
            "theme", "density", "textScale", "animations", "defaultView",
            "weekStartHour", "weekEndHour", "timeFormat", "syncIntervalMinutes",
            "hiddenCalendars",
        ):
            self.assertIn(f"`{key}`", readme)

    def test_public_install_guide_excludes_private_rollback_material(self):
        guide = (ROOT / "docs/INSTALL.md").read_text(encoding="utf-8")
        for retired in (
            "## Update and rollback",
            "calendar.failed",
            "plugin.pre-rc",
        ):
            self.assertNotIn(retired, guide)

    def test_canonical_dataset_has_complete_non_alt_calendar_contract(self):
        data = json.loads(GUIDE_DATA.read_text(encoding="utf-8"))
        self.assertTrue(any(item["id"] == "calendar" for item in data["surfaces"]))
        self.assertTrue(any(item["id"] == "calendar-control" for item in data["workflows"]))
        entries = [item for item in data["shortcuts"] if item["surface"] == "calendar"]
        keys = {item["keys"] for item in entries}
        for required in (
            "t", "w", "j / k or Down / Up", "h / l or Left / Right",
            "[ / ]", "g", "Enter", "m", "o", "c", "s",
            "h / l (Settings)", "j / k (Settings)", "Enter / Space (Settings)",
            "a (Settings)", "r", "?", "Esc",
        ):
            self.assertIn(required, keys)
        self.assertNotIn("J", keys)
        self.assertNotIn("O", keys)
        global_launch = [
            item for item in data["shortcuts"]
            if item["surface"] == "desktop" and item["keys"] == "Super+Shift+C"
        ]
        self.assertEqual(len(global_launch), 1)
        self.assertEqual(global_launch[0]["live_description"], "Flight Deck calendar")
        entries += global_launch
        self.assertTrue(all(item["status"] == "custom" for item in entries))
        self.assertTrue(all("Alt" not in item["keys"] for item in entries))
        self.assertTrue(all("calendar-control" in item["workflows"] for item in entries))

if __name__ == "__main__":
    unittest.main()
