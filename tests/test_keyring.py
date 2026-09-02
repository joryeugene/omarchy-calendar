# SPDX-License-Identifier: GPL-3.0-or-later
import json
import subprocess
import unittest

from omarchy_calendar.keyring import KeyringError, SecretServiceStore, redact


class FakeRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        return self.results.pop(0)


class SecretServiceTests(unittest.TestCase):
    def test_put_and_get_use_attributes_and_standard_input(self):
        token = {"access_token": "access-secret", "refresh_token": "refresh-secret"}
        runner = FakeRunner([
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, json.dumps(token), ""),
        ])
        store = SecretServiceStore(runner=runner)

        store.put("google", "account-1", token)
        restored = store.get("google", "account-1")

        put_argv, put_kwargs = runner.calls[0]
        self.assertEqual(put_argv[0:3], ["secret-tool", "store", "--label=Omarchy Calendar google account-1"])
        self.assertEqual(put_argv[-6:], ["application", "omarchy-calendar", "provider", "google", "account", "account-1"])
        self.assertEqual(json.loads(put_kwargs["input"]), token)
        self.assertNotIn("access-secret", " ".join(put_argv))
        self.assertEqual(restored, token)

    def test_missing_item_returns_none_and_clear_is_scoped(self):
        runner = FakeRunner([
            subprocess.CompletedProcess([], 1, "", "No matching items"),
            subprocess.CompletedProcess([], 0, "", ""),
        ])
        store = SecretServiceStore(runner=runner)

        self.assertIsNone(store.get("microsoft", "personal"))
        store.clear("microsoft", "personal")

        clear_argv = runner.calls[1][0]
        self.assertEqual(clear_argv[0:2], ["secret-tool", "clear"])
        self.assertEqual(clear_argv[-6:], ["application", "omarchy-calendar", "provider", "microsoft", "account", "personal"])

    def test_google_desktop_credential_uses_a_distinct_keyring_item_and_standard_input(self):
        runner = FakeRunner([
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "desktop-credential", ""),
        ])
        store = SecretServiceStore(runner=runner)

        store.put_app_credential("google", "desktop-credential")
        restored = store.get_app_credential("google")

        put_argv, put_kwargs = runner.calls[0]
        self.assertEqual(
            put_argv[-6:],
            ["application", "omarchy-calendar", "provider", "google", "kind", "oauth-client-credential"],
        )
        self.assertEqual(put_kwargs["input"], "desktop-credential")
        self.assertNotIn("desktop-credential", " ".join(put_argv))
        self.assertEqual(restored, "desktop-credential")

    def test_error_redacts_oauth_material(self):
        raw = 'access_token=aaa refresh_token=bbb {"id_token":"ccc","code":"ddd"}'
        cleaned = redact(raw)
        self.assertNotIn("aaa", cleaned)
        self.assertNotIn("bbb", cleaned)
        self.assertNotIn("ccc", cleaned)
        self.assertNotIn("ddd", cleaned)
        self.assertIn("[redacted]", cleaned)

    def test_app_credential_store_error_redacts_the_imported_value(self):
        imported_credential = "user-imported-desktop-credential"

        def runner(_argv, **_kwargs):
            return subprocess.CompletedProcess(
                [], 2, stdout="", stderr=f"store rejected {imported_credential}"
            )

        with self.assertRaises(KeyringError) as caught:
            SecretServiceStore(runner).put_app_credential(
                "google", imported_credential
            )

        self.assertNotIn(imported_credential, str(caught.exception))
        self.assertIn("[redacted]", str(caught.exception))

    def test_provider_and_full_reset_clear_only_calendar_items(self):
        runner = FakeRunner([
            subprocess.CompletedProcess([], 0, "", ""),
            subprocess.CompletedProcess([], 0, "", ""),
        ])
        store = SecretServiceStore(runner=runner)

        store.clear_provider("google")
        store.clear_all()

        self.assertEqual(
            runner.calls[0][0],
            ["secret-tool", "clear", "application", "omarchy-calendar", "provider", "google"],
        )
        self.assertEqual(
            runner.calls[1][0],
            ["secret-tool", "clear", "application", "omarchy-calendar"],
        )


if __name__ == "__main__":
    unittest.main()
