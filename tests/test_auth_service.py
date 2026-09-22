# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import omarchy_calendar.settings as settings_module
from omarchy_calendar.auth_service import Authenticator
from omarchy_calendar import auth_service
from omarchy_calendar.cache import CalendarStore
from omarchy_calendar.cli import seed_demo
from omarchy_calendar.http import HttpError
from omarchy_calendar.models import Account, ProviderHealth
from omarchy_calendar.oauth import (
    GOOGLE_EDIT_SCOPES,
    GOOGLE_SCOPES,
    MICROSOFT_EDIT_SCOPES,
    OAuthError,
    OAuthFlow,
)
from omarchy_calendar.settings import ProviderSettings
from tests.test_sync import FakeHttp, FakeKeyring, FakeProvider, sample_event


class FakeReceiver:
    redirect_uri = "http://127.0.0.1:8765/callback"
    providers = []
    timeouts = []

    def __init__(self, flow, provider):
        self.flow = flow
        self.provider = provider
        self.providers.append(provider)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def wait(self, timeout=180):
        self.timeouts.append(timeout)
        return "authorization-code"


class AuthenticatorTests(unittest.TestCase):
    def setUp(self):
        FakeReceiver.providers.clear()
        FakeReceiver.timeouts.clear()

    def test_google_auth_exchanges_pkce_stores_token_and_initial_events(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring(None, app_credential="desktop-credential")
            http = FakeHttp({
                "access_token": "access", "refresh_token": "refresh", "expires_in": 3600
            })
            provider = FakeProvider((Account("google", "a", "a@example.com"), [sample_event()]))
            opened = []
            auth = Authenticator(
                store, keyring=keyring, http=http,
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": provider}, browser=lambda url: opened.append(url) or True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            seed_demo(store, date(2026, 8, 25))

            result = auth.authenticate("google")

            self.assertEqual(result["account_id"], "a")
            self.assertIn("calendar.events.readonly", opened[0])
            self.assertEqual(FakeReceiver.providers, ["google"])
            self.assertEqual(FakeReceiver.timeouts, [600])
            self.assertEqual(http.posts[0][0], "https://oauth2.googleapis.com/token")
            self.assertEqual(http.posts[0][1]["code_verifier"], "v" * 64)
            self.assertEqual(http.posts[0][1]["client_secret"], "desktop-credential")
            self.assertEqual(keyring.puts[0][0:2], ("google", "a"))
            view = store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
            self.assertEqual([item["uid"] for item in view["events"]], ["google:a:c:fresh"])
            self.assertFalse(view["demo"])
            store.close()

    def test_bundled_google_auth_uses_public_desktop_metadata_and_read_only_scopes(self):
        class NoLocalCredentialKeyring(FakeKeyring):
            def get_app_credential(self, _provider):
                raise AssertionError("bundled auth must not read a local app credential")

        with tempfile.TemporaryDirectory() as temporary, patch.multiple(
            settings_module,
            BUNDLED_PUBLIC_CLIENT_IDS={
                "google": "bundled.apps.googleusercontent.com",
                "microsoft": "",
            },
            BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL="bundled-google-credential",
            create=True,
        ):
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = NoLocalCredentialKeyring(None)
            http = FakeHttp({
                "access_token": "access", "refresh_token": "refresh", "expires_in": 3600
            })
            provider = FakeProvider((Account("google", "a", "a@example.com"), []))
            opened = []
            auth = Authenticator(
                store, keyring=keyring, http=http, settings=ProviderSettings(),
                providers={"google": provider}, browser=lambda url: opened.append(url) or True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            result = auth.authenticate("google")

            self.assertEqual(result["account_id"], "a")
            query = parse_qs(urlparse(opened[0]).query)
            self.assertEqual(set(query["scope"][0].split()), set(GOOGLE_SCOPES))
            self.assertNotIn("auth/calendar ", query["scope"][0] + " ")
            self.assertNotIn("readwrite", query["scope"][0].lower())
            self.assertEqual(
                http.posts[0][1]["client_id"],
                "bundled.apps.googleusercontent.com",
            )
            self.assertEqual(
                http.posts[0][1]["client_secret"],
                "bundled-google-credential",
            )
            store.close()

    def test_local_google_auth_never_mixes_with_bundled_metadata(self):
        with tempfile.TemporaryDirectory() as temporary, patch.multiple(
            settings_module,
            BUNDLED_PUBLIC_CLIENT_IDS={
                "google": "bundled.apps.googleusercontent.com",
                "microsoft": "",
            },
            BUNDLED_GOOGLE_DESKTOP_APP_CREDENTIAL="bundled-google-credential",
            create=True,
        ):
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring(None, app_credential="local-google-credential")
            http = FakeHttp({"access_token": "access", "expires_in": 3600})
            auth = Authenticator(
                store, keyring=keyring, http=http,
                settings=ProviderSettings(
                    google_client_id="local.apps.googleusercontent.com"
                ),
                providers={
                    "google": FakeProvider((Account("google", "a", "a@example.com"), []))
                },
                browser=lambda _url: True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            auth.authenticate("google")

            self.assertEqual(
                http.posts[0][1]["client_id"],
                "local.apps.googleusercontent.com",
            )
            self.assertEqual(
                http.posts[0][1]["client_secret"],
                "local-google-credential",
            )
            store.close()

    def test_personal_microsoft_auth_uses_consumers_for_authorize_and_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring(None, app_credential="desktop-credential")
            http = FakeHttp({
                "access_token": "access", "refresh_token": "refresh", "expires_in": 3600
            })
            provider = FakeProvider((Account("microsoft", "m", "Personal Outlook"), []))
            opened = []
            auth = Authenticator(
                store, keyring=keyring, http=http,
                settings=ProviderSettings(microsoft_client_id="11111111-2222-3333-4444-555555555555"),
                providers={"microsoft": provider}, browser=lambda url: opened.append(url) or True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            result = auth.authenticate("microsoft")

            self.assertEqual(result["account_id"], "m")
            self.assertIn("/consumers/oauth2/v2.0/authorize", opened[0])
            self.assertNotIn("/common/", opened[0])
            self.assertEqual(
                http.posts[0][0],
                "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            )
            self.assertNotIn("client_secret", http.posts[0][1])
            store.close()

    def test_edit_permission_upgrade_rejects_the_wrong_account_without_replacing_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring({
                "access_token": "existing-read-token", "refresh_token": "existing-refresh",
                "expires_at": 9999999999, "access_mode": "read",
            }, app_credential="desktop-credential")
            http = FakeHttp({
                "access_token": "new-edit-token", "expires_in": 3600,
                "scope": " ".join(GOOGLE_EDIT_SCOPES),
            })
            provider = FakeProvider((Account("google", "wrong", "wrong@example.com"), []))
            opened = []
            auth = Authenticator(
                store, keyring=keyring, http=http,
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": provider}, browser=lambda url: opened.append(url) or True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
            )

            with self.assertRaisesRegex(ValueError, "same Google account"):
                auth.authenticate("google", access="edit", expected_account_id="expected")

            self.assertIn("calendar.events.owned", opened[0])
            self.assertEqual(keyring.puts, [])
            self.assertEqual(keyring.token["access_token"], "existing-read-token")
            store.close()

    def test_edit_permission_upgrade_marks_token_only_after_provider_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring(None, app_credential="desktop-credential")
            auth = Authenticator(
                store, keyring=keyring,
                http=FakeHttp({
                    "access_token": "edit", "refresh_token": "refresh", "expires_in": 3600,
                    "scope": " ".join(GOOGLE_EDIT_SCOPES),
                }),
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider((Account("google", "a", "a@example.com"), []))},
                browser=lambda _url: True, receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
            )

            result = auth.authenticate("google", access="edit", expected_account_id="a")

            self.assertEqual(result["access"], "edit")
            self.assertEqual(keyring.puts[0][2]["access_mode"], "edit")
            store.close()

    def test_edit_permission_upgrade_rejects_missing_write_scope_before_storage(self):
        cases = (
            (
                "google",
                ProviderSettings(google_client_id="google-client"),
                "https://www.googleapis.com/auth/calendar.events.readonly",
                "Google",
            ),
            (
                "microsoft",
                ProviderSettings(microsoft_client_id="11111111-2222-3333-4444-555555555555"),
                "Calendars.Read",
                "Outlook",
            ),
        )
        for provider_name, settings, granted_scope, label in cases:
            with self.subTest(provider=provider_name), tempfile.TemporaryDirectory() as temporary:
                store = CalendarStore(Path(temporary) / "calendar.db")
                original = {
                    "access_token": "existing-read-token",
                    "refresh_token": "existing-refresh",
                    "expires_at": 9999999999,
                    "access_mode": "read",
                }
                keyring = FakeKeyring(dict(original), app_credential="desktop-credential")
                provider_api = FakeProvider((
                    Account(provider_name, "account", "person@example.com"), []
                ))
                auth = Authenticator(
                    store,
                    keyring=keyring,
                    http=FakeHttp({
                        "access_token": "new-edit-token",
                        "expires_in": 3600,
                        "scope": granted_scope,
                    }),
                    settings=settings,
                    providers={provider_name: provider_api},
                    browser=lambda _url: True,
                    receiver_factory=FakeReceiver,
                    flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                    now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
                )

                with self.assertRaisesRegex(PermissionError, f"{label}.*edit permission"):
                    auth.authenticate(
                        provider_name, access="edit", expected_account_id="account"
                    )

                self.assertEqual(keyring.puts, [])
                self.assertEqual(keyring.token, original)
                self.assertFalse(hasattr(provider_api, "last_token"))
                self.assertEqual(store.health_records(), [])
                store.close()

    def test_microsoft_edit_permission_upgrade_accepts_exact_write_scope(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring(None)
            auth = Authenticator(
                store,
                keyring=keyring,
                http=FakeHttp({
                    "access_token": "edit",
                    "refresh_token": "refresh",
                    "expires_in": 3600,
                    "scope": " ".join(MICROSOFT_EDIT_SCOPES),
                }),
                settings=ProviderSettings(
                    microsoft_client_id="11111111-2222-3333-4444-555555555555"
                ),
                providers={
                    "microsoft": FakeProvider((
                        Account("microsoft", "account", "person@outlook.example"), []
                    ))
                },
                browser=lambda _url: True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
            )

            result = auth.authenticate(
                "microsoft", access="edit", expected_account_id="account"
            )

            self.assertEqual(result["access"], "edit")
            self.assertEqual(keyring.puts[0][2]["scope"], " ".join(MICROSOFT_EDIT_SCOPES))
            store.close()

    def test_edit_permission_upgrade_treats_omitted_scope_as_the_requested_grant(self):
        cases = (
            ("google", ProviderSettings(google_client_id="google-client"), GOOGLE_EDIT_SCOPES),
            (
                "microsoft",
                ProviderSettings(microsoft_client_id="11111111-2222-3333-4444-555555555555"),
                MICROSOFT_EDIT_SCOPES,
            ),
        )
        for provider_name, settings, requested_scopes in cases:
            with self.subTest(provider=provider_name), tempfile.TemporaryDirectory() as temporary:
                store = CalendarStore(Path(temporary) / "calendar.db")
                keyring = FakeKeyring(None, app_credential="desktop-credential")
                auth = Authenticator(
                    store,
                    keyring=keyring,
                    http=FakeHttp({"access_token": "edit", "expires_in": 3600}),
                    settings=settings,
                    providers={
                        provider_name: FakeProvider((
                            Account(provider_name, "account", "person@example.com"), []
                        ))
                    },
                    browser=lambda _url: True,
                    receiver_factory=FakeReceiver,
                    flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                    now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
                )

                auth.authenticate(provider_name, access="edit", expected_account_id="account")

                self.assertEqual(keyring.puts[0][2]["scope"], " ".join(requested_scopes))
                store.close()

    def test_edit_permission_upgrade_preserves_an_existing_refresh_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            keyring = FakeKeyring({
                "access_token": "read", "refresh_token": "existing-refresh",
                "expires_at": 9999999999, "access_mode": "read",
            }, app_credential="desktop-credential")
            auth = Authenticator(
                store, keyring=keyring,
                http=FakeHttp({
                    "access_token": "edit", "expires_in": 3600,
                    "scope": " ".join(GOOGLE_EDIT_SCOPES),
                }),
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider((Account("google", "a", "a@example.com"), []))},
                browser=lambda _url: True, receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
            )

            auth.authenticate("google", access="edit", expected_account_id="a")

            self.assertEqual(keyring.puts[0][2]["refresh_token"], "existing-refresh")
            store.close()

    def test_edit_permission_denial_preserves_the_read_only_account(self):
        class DenyingReceiver:
            redirect_uri = "http://127.0.0.1:8765/callback"

            def __init__(self, _flow, _provider):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def wait(self, timeout=180):
                raise OAuthError("Provider rejected authorization: User cancelled")

        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            window = ("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
            cached = sample_event("google:a:c:cached")
            store.replace_window(
                "google", "a", *window, [cached],
                ProviderHealth.ok("google", "a", window[0]),
            )
            original_token = {
                "access_token": "existing-read-token",
                "refresh_token": "existing-refresh",
                "expires_at": 9999999999,
                "access_mode": "read",
            }
            keyring = FakeKeyring(dict(original_token), app_credential="desktop-credential")
            http = FakeHttp({"access_token": "must-not-be-used"})
            opened = []
            auth = Authenticator(
                store,
                keyring=keyring,
                http=http,
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider()},
                browser=lambda url: opened.append(url) or True,
                receiver_factory=DenyingReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
            )

            with self.assertRaisesRegex(OAuthError, "User cancelled"):
                auth.authenticate("google", access="edit", expected_account_id="a")

            self.assertIn("calendar.events.owned", opened[0])
            self.assertEqual(http.posts, [])
            self.assertEqual(keyring.puts, [])
            self.assertEqual(keyring.token, original_token)
            self.assertEqual(
                [event["uid"] for event in store.view(*window)["events"]],
                [cached.uid],
            )
            store.close()

    def test_google_auth_without_desktop_credential_fails_before_browser_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            opened = []
            auth = Authenticator(
                store,
                keyring=FakeKeyring(None),
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider()},
                browser=lambda url: opened.append(url) or True,
            )

            with self.assertRaisesRegex(ValueError, "Desktop credentials"):
                auth.authenticate("google")

            self.assertEqual(opened, [])
            store.close()

    def test_failed_authentication_preserves_demo_data(self):
        class FailingHttp:
            def post_token(self, _url, _form):
                raise RuntimeError("exchange failed")

        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            seed_demo(store, date(2026, 8, 25))
            auth = Authenticator(
                store,
                keyring=FakeKeyring(None, app_credential="desktop-credential"),
                http=FailingHttp(),
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider()}, browser=lambda _url: True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            with self.assertRaisesRegex(RuntimeError, "exchange failed"):
                auth.authenticate("google")

            view = store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
            self.assertTrue(view["demo"])
            self.assertEqual(len(view["events"]), 10)
            store.close()

    def test_offline_initial_provider_read_stores_no_token_and_preserves_demo(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            seed_demo(store, date(2026, 8, 25))
            keyring = FakeKeyring(None, app_credential="desktop-credential")
            auth = Authenticator(
                store,
                keyring=keyring,
                http=FakeHttp({
                    "access_token": "access", "refresh_token": "refresh", "expires_in": 3600
                }),
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider(error=HttpError(0, "offline"))},
                browser=lambda _url: True,
                receiver_factory=FakeReceiver,
                flow_factory=lambda: OAuthFlow.for_test(verifier="v" * 64, state="state"),
                now=lambda: datetime(2026, 8, 25, 12, tzinfo=timezone.utc),
            )

            with self.assertRaisesRegex(HttpError, "offline"):
                auth.authenticate("google")

            self.assertEqual(keyring.puts, [])
            view = store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
            self.assertTrue(view["demo"])
            self.assertEqual(len(view["events"]), 10)
            store.close()

    def test_browser_launch_failure_stores_no_token_and_preserves_demo(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = CalendarStore(Path(temporary) / "calendar.db")
            seed_demo(store, date(2026, 8, 25))
            keyring = FakeKeyring(None, app_credential="desktop-credential")
            auth = Authenticator(
                store,
                keyring=keyring,
                settings=ProviderSettings(google_client_id="google-client"),
                providers={"google": FakeProvider()},
                browser=lambda _url: False,
                receiver_factory=FakeReceiver,
            )

            with self.assertRaisesRegex(RuntimeError, "Could not open the browser"):
                auth.authenticate("google")

            self.assertEqual(keyring.puts, [])
            view = store.view("2026-08-25T00:00:00Z", "2026-08-26T00:00:00Z")
            self.assertTrue(view["demo"])
            self.assertEqual(len(view["events"]), 10)
            store.close()


class SystemBrowserTests(unittest.TestCase):
    def test_prefers_the_omarchy_launcher_that_focuses_the_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            launcher = Path(directory) / "omarchy-launch-browser"
            launcher.write_text("#!/bin/sh\n", encoding="utf-8")
            launcher.chmod(0o755)
            with patch.dict("os.environ", {"PATH": directory}, clear=False):
                with patch.dict("os.environ", {"OMARCHY_CALENDAR_BROWSER_COMMAND": ""}, clear=False):
                    with patch.object(auth_service, "_spawn_browser", return_value=True) as spawn:
                        self.assertTrue(auth_service.open_system_browser("https://example.test"))
        spawn.assert_called_once_with([str(launcher), "https://example.test"])

    def test_override_command_takes_precedence(self):
        with patch.dict(
            "os.environ",
            {"OMARCHY_CALENDAR_BROWSER_COMMAND": "custom-browser --incognito"},
            clear=False,
        ):
            with patch.object(auth_service, "_spawn_browser", return_value=True) as spawn:
                self.assertTrue(auth_service.open_system_browser("https://example.test"))
        spawn.assert_called_once_with(["custom-browser", "--incognito", "https://example.test"])

    def test_falls_back_to_the_standard_library_without_a_launcher(self):
        with patch.dict("os.environ", {}, clear=True):
            with patch.object(auth_service.shutil, "which", return_value=None):
                with patch.object(auth_service.webbrowser, "open", return_value=True) as opened:
                    self.assertTrue(auth_service.open_system_browser("https://example.test"))
        opened.assert_called_once_with("https://example.test")


if __name__ == "__main__":
    unittest.main()
