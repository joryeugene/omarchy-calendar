# SPDX-License-Identifier: GPL-3.0-or-later
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import omarchy_calendar.settings as settings_module
from omarchy_calendar.auth_service import Authenticator
from omarchy_calendar.cache import CalendarStore
from omarchy_calendar.cli import seed_demo
from omarchy_calendar.http import HttpError
from omarchy_calendar.models import Account
from omarchy_calendar.oauth import GOOGLE_SCOPES, OAuthFlow
from omarchy_calendar.settings import ProviderSettings
from tests.test_sync import FakeHttp, FakeKeyring, FakeProvider, sample_event


class FakeReceiver:
    redirect_uri = "http://127.0.0.1:8765/callback"
    providers = []

    def __init__(self, flow, provider):
        self.flow = flow
        self.provider = provider
        self.providers.append(provider)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def wait(self, timeout=180):
        return "authorization-code"


class AuthenticatorTests(unittest.TestCase):
    def setUp(self):
        FakeReceiver.providers.clear()

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


if __name__ == "__main__":
    unittest.main()
