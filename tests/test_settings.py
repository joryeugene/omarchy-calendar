# SPDX-License-Identifier: GPL-3.0-or-later
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import omarchy_calendar.settings as settings_module
from omarchy_calendar.settings import ProviderSettings


class ProviderSettingsTests(unittest.TestCase):
    def test_bundled_registration_defaults_stay_empty_until_production_values_exist(self):
        self.assertEqual(settings_module.BUNDLED_PUBLIC_CLIENT_IDS, {
            "google": "",
            "microsoft": "",
        })
        self.assertEqual(settings_module.BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL, "")

    def test_loads_only_public_client_identifiers(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "providers.json"
            path.write_text(json.dumps({
                "google": {"client_id": "google-public"},
                "microsoft": {"client_id": "microsoft-public"},
            }))

            settings = ProviderSettings.load(path)

        self.assertEqual(settings.google_client_id, "google-public")
        self.assertEqual(settings.microsoft_client_id, "microsoft-public")
        self.assertNotIn("secret", repr(settings).lower())

    def test_missing_file_produces_disconnected_configuration(self):
        settings = ProviderSettings.load(Path("/definitely/missing/providers.json"))
        self.assertEqual(settings.google_client_id, "")
        self.assertEqual(settings.microsoft_client_id, "")

    def test_bundled_public_ids_are_defaults_and_local_overrides_win(self):
        with patch.multiple(
            settings_module,
            BUNDLED_PUBLIC_CLIENT_IDS={
                "google": "bundled.apps.googleusercontent.com",
                "microsoft": "00001111-aaaa-2222-bbbb-3333cccc4444",
            },
            BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL="bundled-google-credential",
            create=True,
        ):
            bundled = ProviderSettings()
            google_override = ProviderSettings(
                google_client_id="local.apps.googleusercontent.com"
            )
            microsoft_override = ProviderSettings(
                microsoft_client_id="55555555-6666-7777-8888-999999999999"
            )

            class FakeKeyring:
                def __init__(self, credential):
                    self.credential = credential
                    self.lookups = []

                def get_app_credential(self, provider):
                    self.lookups.append(provider)
                    return self.credential

            bundled_keyring = FakeKeyring("must-not-be-used")
            local_keyring = FakeKeyring("local-google-credential")
            missing_local_keyring = FakeKeyring("")

            self.assertEqual(bundled.client_id("google"), "bundled.apps.googleusercontent.com")
            self.assertEqual(
                bundled.client_id("microsoft"),
                "00001111-aaaa-2222-bbbb-3333cccc4444",
            )
            self.assertEqual(
                bundled.google_app_credential(bundled_keyring),
                "bundled-google-credential",
            )
            self.assertEqual(bundled_keyring.lookups, [])
            self.assertEqual(bundled.registration_source("google"), "bundled")
            self.assertEqual(bundled.registration_source("microsoft"), "bundled")

            self.assertEqual(
                google_override.client_id("google"),
                "local.apps.googleusercontent.com",
            )
            self.assertEqual(
                google_override.google_app_credential(local_keyring),
                "local-google-credential",
            )
            self.assertEqual(local_keyring.lookups, ["google"])
            self.assertEqual(google_override.registration_source("google"), "local")

            self.assertEqual(
                google_override.google_app_credential(missing_local_keyring),
                "",
            )
            self.assertEqual(missing_local_keyring.lookups, ["google"])
            self.assertEqual(
                microsoft_override.client_id("microsoft"),
                "55555555-6666-7777-8888-999999999999",
            )
            self.assertEqual(microsoft_override.registration_source("microsoft"), "local")

    def test_updates_one_public_client_id_with_private_atomic_storage(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "private" / "providers.json"
            saved = ProviderSettings(microsoft_client_id="microsoft-public").with_client_id(
                "google", "google-public.apps.googleusercontent.com"
            ).save(path)

            loaded = ProviderSettings.load(saved)
            self.assertEqual(loaded.google_client_id, "google-public.apps.googleusercontent.com")
            self.assertEqual(loaded.microsoft_client_id, "microsoft-public")
            self.assertEqual(os.stat(path.parent).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_invalid_public_id_does_not_replace_existing_settings(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "providers.json"
            ProviderSettings(
                google_client_id="known-good.apps.googleusercontent.com",
                microsoft_client_id="00001111-aaaa-2222-bbbb-3333cccc4444",
            ).save(path)
            original = path.read_bytes()

            invalid_ids = (
                ("google", ""),
                ("google", "line-one\nline-two"),
                ("google", "x" * 513),
                ("google", "not-a-public-client-id"),
                ("google", "arbitrary-public-looking-value"),
                ("microsoft", "arbitrary-public-looking-value"),
                ("microsoft", "known-good.apps.googleusercontent.com"),
            )
            for provider, invalid in invalid_ids:
                with self.subTest(provider=provider, invalid=invalid[:32]):
                    with self.assertRaises(ValueError):
                        ProviderSettings.load(path).with_client_id(provider, invalid).save(path)
                    self.assertEqual(path.read_bytes(), original)

    def test_accepts_and_normalizes_provider_specific_public_client_ids(self):
        settings = ProviderSettings().with_client_id(
            "google", "  123456-example.apps.googleusercontent.com  "
        ).with_client_id(
            "microsoft", "00001111-AAAA-2222-BBBB-3333CCCC4444"
        )

        self.assertEqual(
            settings.google_client_id,
            "123456-example.apps.googleusercontent.com",
        )
        self.assertEqual(
            settings.microsoft_client_id,
            "00001111-aaaa-2222-bbbb-3333cccc4444",
        )

    def test_clear_removes_only_the_local_provider_override_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "omarchy-calendar" / "providers.json"
            appearance = root / "omarchy-calendar" / "appearance.json"
            ProviderSettings(google_client_id="known.apps.googleusercontent.com").save(path)
            appearance.write_text('{"theme":"high-contrast"}\n', encoding="utf-8")

            removed = ProviderSettings.clear(path)

            self.assertTrue(removed)
            self.assertFalse(path.exists())
            self.assertTrue(appearance.is_file())


if __name__ == "__main__":
    unittest.main()
