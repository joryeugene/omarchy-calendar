# SPDX-License-Identifier: GPL-3.0-or-later
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).parents[1]
GUIDE_DATA = ROOT / "docs" / "shortcuts.json"
SITE = ROOT / "site"


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.targets = []

    def handle_starttag(self, tag, attributes):
        attribute_name = "src" if tag == "img" else "href" if tag in {"a", "link"} else ""
        values = dict(attributes)
        if attribute_name and values.get(attribute_name):
            self.targets.append(values[attribute_name])


class DocumentationTests(unittest.TestCase):
    def test_static_site_local_navigation_resolves_from_each_public_page(self):
        pages = (SITE / "index.html", SITE / "privacy" / "index.html")
        for page in pages:
            self.assertTrue(page.is_file(), page)
            parser = LinkParser()
            parser.feed(page.read_text(encoding="utf-8"))
            for target in parser.targets:
                parsed = urlsplit(target)
                if parsed.scheme or parsed.netloc or target.startswith("#"):
                    continue
                self.assertFalse(parsed.path.startswith("/"), (page, target))
                resolved = (page.parent / unquote(parsed.path)).resolve()
                self.assertTrue(resolved.is_relative_to(SITE.resolve()), (page, target))
                if resolved.is_dir():
                    resolved /= "index.html"
                self.assertTrue(resolved.is_file(), (page, target))

    def test_static_site_explains_preview_access_storage_and_deletion_behavior(self):
        homepage_path = SITE / "index.html"
        privacy_path = SITE / "privacy" / "index.html"
        self.assertTrue(homepage_path.is_file(), homepage_path)
        self.assertTrue(privacy_path.is_file(), privacy_path)
        homepage = homepage_path.read_text(encoding="utf-8")
        privacy = privacy_path.read_text(encoding="utf-8")
        public_copy = homepage + privacy

        for required in (
            "omarchy plugin add https://github.com/joryeugene/omarchy-calendar.git --enable",
            "Bring your own desktop OAuth registration",
            "Google Desktop OAuth app",
            "Microsoft public desktop app",
            "not one-click or seamless",
            "https://www.googleapis.com/auth/calendar.events.readonly",
            "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
            "openid",
            "email",
            "profile",
            "offline_access",
            "User.Read",
            "Calendars.Read",
            "Secret Service",
            "~/.local/state/omarchy-calendar/calendar.db",
            "last successful local cache",
            "marked stale",
            "Disconnecting Google or Outlook deletes",
            "calendarctl reset-local-data",
            "two confirmations",
            "Uninstalling the plugin alone does not delete data",
        ):
            self.assertIn(required, public_copy)
        for forbidden in (
            "Calendars.ReadWrite",
            "https://www.googleapis.com/auth/calendar</code>",
            "https://www.googleapis.com/auth/calendar.events</code>",
            "one-click account setup",
        ):
            self.assertNotIn(forbidden, public_copy)

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
