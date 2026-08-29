# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import omarchy_calendar.settings as settings_module
from omarchy_calendar.cache import CalendarStore
from omarchy_calendar.cli import import_google_desktop_app, open_event_url, reset_local_data, seed_demo, setup_status
from omarchy_calendar.models import ProviderHealth
from omarchy_calendar.settings import ProviderSettings


ROOT = Path(__file__).parents[1]


class CalendarCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "state"
        self.config = Path(self.temp.name) / "config"

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        env = os.environ.copy()
        env.update({
            "PYTHONPATH": str(ROOT / "src"),
            "XDG_STATE_HOME": str(self.state),
            "XDG_CONFIG_HOME": str(self.config),
        })
        return subprocess.run(
            [sys.executable, str(ROOT / "calendarctl"), *args],
            text=True, capture_output=True, env=env, check=False,
        )

    def test_demo_seed_view_status_and_clear(self):
        seeded = self.run_cli("demo", "seed", "--date", "2026-08-25")
        self.assertEqual(seeded.returncode, 0, seeded.stderr)
        self.assertEqual(json.loads(seeded.stdout)["seeded"], 25)

        view = self.run_cli(
            "view", "--from", "2026-08-25T00:00:00-05:00",
            "--to", "2026-08-26T00:00:00-05:00",
        )
        payload = json.loads(view.stdout)
        self.assertTrue(payload["demo"])
        self.assertEqual({event["provider"] for event in payload["events"]}, {"google", "microsoft"})

        status = self.run_cli("status")
        self.assertEqual(len(json.loads(status.stdout)["providers"]), 2)

        cleared = self.run_cli("demo", "clear")
        self.assertEqual(json.loads(cleared.stdout)["cleared_accounts"], 2)

    def test_auth_without_public_client_id_fails_before_browser_open(self):
        result = self.run_cli("auth", "google")
        self.assertEqual(result.returncode, 3)
        self.assertIn("public client ID is not configured", result.stderr)
        self.assertNotIn("token", result.stderr.lower())

    def test_public_cli_exposes_no_client_secret_configuration(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for forbidden in (
            "configure-client-secret", "open-provider-setup",
            "create-event", "update-event", "delete-event",
        ):
            self.assertNotIn(forbidden, result.stdout)

    def test_configure_client_and_setup_status_separate_configuration_from_connection(self):
        configured = self.run_cli(
            "configure-client", "microsoft", "11111111-2222-3333-4444-555555555555"
        )
        self.assertEqual(configured.returncode, 0, configured.stderr)
        self.assertEqual(json.loads(configured.stdout), {"provider": "microsoft", "configured": True})

        initial = json.loads(self.run_cli("setup-status").stdout)
        google = next(item for item in initial["providers"] if item["provider"] == "google")
        outlook = next(item for item in initial["providers"] if item["provider"] == "microsoft")
        self.assertFalse(google["client_configured"])
        self.assertFalse(google["connected"])
        self.assertTrue(outlook["client_configured"])
        self.assertNotIn("client_id", outlook)

        with CalendarStore(self.state / "omarchy-calendar" / "calendar.db") as store:
            store.set_health(ProviderHealth.ok("microsoft", "real-account", "2026-08-25T12:00:00Z"))
        connected = json.loads(self.run_cli("setup-status").stdout)
        outlook = next(item for item in connected["providers"] if item["provider"] == "microsoft")
        self.assertTrue(outlook["connected"])
        self.assertEqual(outlook["accounts"], 1)

    def test_configure_client_rejects_google_without_desktop_json(self):
        result = self.run_cli(
            "configure-client", "google", "google-public.apps.googleusercontent.com"
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid choice", result.stderr)

    def test_setup_status_requires_google_desktop_credential(self):
        class FakeKeyring:
            def __init__(self, credential):
                self.credential = credential

            def get_app_credential(self, provider):
                self.assert_provider = provider
                return self.credential

        settings = ProviderSettings(google_client_id="local.apps.googleusercontent.com")
        with CalendarStore(self.state / "omarchy-calendar" / "calendar.db") as store:
            missing = setup_status(store, settings, FakeKeyring(""))
            ready = setup_status(store, settings, FakeKeyring("desktop-credential"))

        missing_google = next(item for item in missing["providers"] if item["provider"] == "google")
        ready_google = next(item for item in ready["providers"] if item["provider"] == "google")
        self.assertFalse(missing_google["client_configured"])
        self.assertTrue(ready_google["client_configured"])
        self.assertEqual(missing_google["registration_source"], "local")
        self.assertEqual(ready_google["registration_source"], "local")

    def test_setup_status_counts_complete_bundles_without_exposing_registration_values(self):
        bundled_values = {
            "google": "bundled.apps.googleusercontent.com",
            "microsoft": "00001111-aaaa-2222-bbbb-3333cccc4444",
        }
        bundled_credential = "bundled-google-credential"

        class NoLocalCredentialKeyring:
            def get_app_credential(self, _provider):
                raise AssertionError("bundled Google setup must not read a local credential")

        with patch.multiple(
            settings_module,
            BUNDLED_PUBLIC_CLIENT_IDS=bundled_values,
            BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL=bundled_credential,
            create=True,
        ), CalendarStore(self.state / "omarchy-calendar" / "calendar.db") as store:
            status = setup_status(store, ProviderSettings(), NoLocalCredentialKeyring())

        google = next(item for item in status["providers"] if item["provider"] == "google")
        microsoft = next(
            item for item in status["providers"] if item["provider"] == "microsoft"
        )
        self.assertTrue(google["client_configured"])
        self.assertEqual(google["registration_source"], "bundled")
        self.assertTrue(microsoft["client_configured"])
        self.assertEqual(microsoft["registration_source"], "bundled")
        serialized = json.dumps(status)
        self.assertNotIn(bundled_values["google"], serialized)
        self.assertNotIn(bundled_values["microsoft"], serialized)
        self.assertNotIn(bundled_credential, serialized)

    def test_setup_status_never_completes_a_local_google_id_with_bundled_credential(self):
        class MissingLocalCredentialKeyring:
            def get_app_credential(self, provider):
                self.provider = provider
                return ""

        keyring = MissingLocalCredentialKeyring()
        with patch.multiple(
            settings_module,
            BUNDLED_PUBLIC_CLIENT_IDS={
                "google": "bundled.apps.googleusercontent.com",
                "microsoft": "",
            },
            BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL="bundled-google-credential",
            create=True,
        ), CalendarStore(self.state / "omarchy-calendar" / "calendar.db") as store:
            status = setup_status(
                store,
                ProviderSettings(google_client_id="local.apps.googleusercontent.com"),
                keyring,
            )

        google = next(item for item in status["providers"] if item["provider"] == "google")
        self.assertFalse(google["client_configured"])
        self.assertEqual(google["registration_source"], "local")
        self.assertEqual(keyring.provider, "google")

    def test_import_google_desktop_app_keeps_credential_out_of_settings_and_result(self):
        class FakeKeyring:
            def __init__(self):
                self.puts = []

            def put_app_credential(self, provider, credential):
                self.puts.append((provider, credential))

        source = Path(self.temp.name) / "desktop.json"
        source.write_text(json.dumps({
            "installed": {
                "client_id": "local.apps.googleusercontent.com",
                "client_secret": "desktop-credential",
                "redirect_uris": ["http://localhost"],
            }
        }), encoding="utf-8")
        settings_path = self.config / "omarchy-calendar" / "providers.json"
        keyring = FakeKeyring()

        result = import_google_desktop_app(source, keyring, settings_path)

        self.assertEqual(result, {"provider": "google", "configured": True})
        self.assertEqual(keyring.puts, [("google", "desktop-credential")])
        saved = json.loads(settings_path.read_text(encoding="utf-8"))
        self.assertEqual(saved["google"]["client_id"], "local.apps.googleusercontent.com")
        self.assertNotIn("client_secret", settings_path.read_text(encoding="utf-8"))
        self.assertNotIn("desktop-credential", json.dumps(result))

    def test_import_google_desktop_app_accepts_qml_file_url(self):
        class FakeKeyring:
            def __init__(self):
                self.puts = []

            def put_app_credential(self, provider, credential):
                self.puts.append((provider, credential))

        source = Path(self.temp.name) / "Google Desktop credentials.json"
        source.write_text(json.dumps({
            "installed": {
                "client_id": "local.apps.googleusercontent.com",
                "client_secret": "desktop-credential",
            }
        }), encoding="utf-8")
        settings_path = self.config / "omarchy-calendar" / "providers.json"
        keyring = FakeKeyring()

        result = import_google_desktop_app(source.as_uri(), keyring, settings_path)

        self.assertEqual(result, {"provider": "google", "configured": True})
        self.assertEqual(keyring.puts, [("google", "desktop-credential")])

    def test_import_google_desktop_app_rejects_nonlocal_url(self):
        class FakeKeyring:
            def put_app_credential(self, provider, credential):
                raise AssertionError("remote input must not reach the keyring")

        with self.assertRaisesRegex(ValueError, "local file"):
            import_google_desktop_app(
                "https://example.com/google-desktop.json",
                FakeKeyring(),
                self.config / "omarchy-calendar" / "providers.json",
            )

    def test_import_google_desktop_app_rejects_ambiguous_file_url(self):
        class FakeKeyring:
            def put_app_credential(self, provider, credential):
                raise AssertionError("ambiguous input must not reach the keyring")

        source = Path(self.temp.name) / "desktop.json"
        source.write_text(json.dumps({
            "installed": {
                "client_id": "local.apps.googleusercontent.com",
                "client_secret": "desktop-credential",
            }
        }), encoding="utf-8")

        for suffix in ("?download=1", "#credential"):
            with self.subTest(suffix=suffix), self.assertRaisesRegex(ValueError, "plain local file"):
                import_google_desktop_app(
                    source.as_uri() + suffix,
                    FakeKeyring(),
                    self.config / "omarchy-calendar" / "providers.json",
                )

    def test_import_google_desktop_app_rejects_nonregular_or_oversized_file(self):
        class FakeKeyring:
            def put_app_credential(self, provider, credential):
                raise AssertionError("invalid input must not reach the keyring")

        settings_path = self.config / "omarchy-calendar" / "providers.json"
        with self.assertRaisesRegex(ValueError, "regular file"):
            import_google_desktop_app(Path(self.temp.name), FakeKeyring(), settings_path)

        source = Path(self.temp.name) / "oversized.json"
        source.write_text(json.dumps({
            "installed": {
                "client_id": "local.apps.googleusercontent.com",
                "client_secret": "desktop-credential",
            },
            "padding": "x" * 70000,
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "too large"):
            import_google_desktop_app(source, FakeKeyring(), settings_path)

    def test_failed_google_desktop_import_preserves_existing_settings(self):
        class FakeKeyring:
            def __init__(self):
                self.puts = []

            def put_app_credential(self, provider, credential):
                self.puts.append((provider, credential))

        settings_path = self.config / "omarchy-calendar" / "providers.json"
        settings_path.parent.mkdir(parents=True)
        original = '{"microsoft":{"client_id":"11111111-2222-3333-4444-555555555555"}}\n'
        settings_path.write_text(original, encoding="utf-8")
        source = Path(self.temp.name) / "malformed.json"
        source.write_text("not json", encoding="utf-8")
        keyring = FakeKeyring()

        with self.assertRaisesRegex(ValueError, "not valid JSON"):
            import_google_desktop_app(source, keyring, settings_path)

        self.assertEqual(settings_path.read_text(encoding="utf-8"), original)
        self.assertEqual(keyring.puts, [])

    def test_open_action_passes_cached_https_url_without_a_shell(self):
        store = CalendarStore(self.state / "open-test.db")
        seed_demo(store, __import__("datetime").date(2026, 8, 25))
        uid = store.view("2026-08-25T00:00:00-05:00", "2026-08-26T00:00:00-05:00")["events"][0]["uid"]
        calls = []

        result = open_event_url(
            store, uid, "provider_url", command="test-browser",
            runner=lambda argv, **kwargs: calls.append((argv, kwargs)),
        )

        self.assertEqual(result, 0)
        self.assertEqual(calls[0][0][0], "test-browser")
        self.assertTrue(calls[0][0][1].startswith("https://"))
        self.assertNotIn("shell", calls[0][1])
        store.close()

    def test_reset_local_data_clears_cache_tokens_and_provider_overrides(self):
        class FakeKeyring:
            def __init__(self):
                self.cleared = False

            def clear_all(self):
                self.cleared = True

        settings_path = self.config / "omarchy-calendar" / "providers.json"
        settings_path.parent.mkdir(parents=True)
        settings_path.write_text('{"google":{"client_id":"public"}}\n', encoding="utf-8")
        appearance_path = settings_path.parent / "appearance.json"
        appearance_path.write_text('{"theme":"high-contrast"}\n', encoding="utf-8")
        keyring = FakeKeyring()
        with CalendarStore(self.state / "omarchy-calendar" / "calendar.db") as store:
            store.set_health(ProviderHealth.ok("google", "real-account", "2026-08-25T12:00:00Z"))

            result = reset_local_data(store, keyring, settings_path)

            self.assertEqual(result["providers"], 1)
            self.assertEqual(store.health_records(), [])
        self.assertTrue(keyring.cleared)
        self.assertFalse(settings_path.exists())
        self.assertTrue(appearance_path.is_file())


if __name__ == "__main__":
    unittest.main()
