# SPDX-License-Identifier: GPL-3.0-or-later
import base64
import hashlib
import threading
import unittest
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlparse

from omarchy_calendar.oauth import (
    GOOGLE_SCOPES,
    MICROSOFT_SCOPES,
    LoopbackReceiver,
    OAuthError,
    OAuthFlow,
    OAuthStateError,
    authorization_url,
)


class OAuthTests(unittest.TestCase):
    def test_pkce_is_s256_and_state_is_verified(self):
        flow = OAuthFlow.for_test(verifier="a" * 64, state="state-123")
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(("a" * 64).encode()).digest()
        ).decode().rstrip("=")

        self.assertEqual(flow.challenge, expected)
        self.assertEqual(flow.verify_callback({"state": ["state-123"], "code": ["ok"]}), "ok")
        with self.assertRaises(OAuthStateError):
            flow.verify_callback({"state": ["wrong"], "code": ["ok"]})

    def test_google_authorization_uses_only_identity_and_read_only_calendar_scopes(self):
        url = authorization_url(
            "google", "google-public-id", "http://127.0.0.1:8123/callback",
            OAuthFlow.for_test(verifier="b" * 64, state="google-state"),
        )
        query = parse_qs(urlparse(url).query)

        self.assertEqual(set(query["scope"][0].split()), set(GOOGLE_SCOPES))
        self.assertIn("calendar.events.readonly", query["scope"][0])
        self.assertIn("calendar.calendarlist.readonly", query["scope"][0])
        self.assertNotIn("auth/calendar ", query["scope"][0] + " ")
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["access_type"], ["offline"])

    def test_microsoft_authorization_supports_personal_accounts_without_write_scope(self):
        url = authorization_url(
            "microsoft", "microsoft-public-id", "http://127.0.0.1:8123/callback",
            OAuthFlow.for_test(verifier="c" * 64, state="microsoft-state"),
        )
        parsed = urlparse(url)
        query = parse_qs(parsed.query)

        self.assertIn("/consumers/oauth2/v2.0/authorize", parsed.path)
        self.assertNotIn("/common/", parsed.path)
        self.assertEqual(set(query["scope"][0].split()), set(MICROSOFT_SCOPES))
        self.assertIn("Calendars.Read", query["scope"][0])
        self.assertNotIn("ReadWrite", query["scope"][0])
        self.assertNotIn("Mail.", query["scope"][0])
        self.assertEqual(query["code_challenge_method"], ["S256"])

    def test_loopback_receiver_accepts_one_valid_callback(self):
        flow = OAuthFlow.for_test(verifier="d" * 64, state="loopback-state")
        with LoopbackReceiver(flow) as receiver:
            callback = receiver.redirect_uri + "?state=loopback-state&code=auth-code"
            request = threading.Thread(target=lambda: urllib.request.urlopen(callback, timeout=2).read())
            request.start()
            code = receiver.wait(timeout=2)
            request.join(timeout=2)

        self.assertEqual(code, "auth-code")
        self.assertFalse(request.is_alive())

    def test_microsoft_loopback_matches_the_portal_mobile_desktop_redirect(self):
        flow = OAuthFlow.for_test(verifier="e" * 64, state="microsoft-loopback")
        with LoopbackReceiver(flow, "microsoft") as receiver:
            parsed = urlparse(receiver.redirect_uri)
            self.assertEqual(parsed.hostname, "localhost")
            self.assertEqual(parsed.path, "")
            callback = receiver.redirect_uri + "?state=microsoft-loopback&code=auth-code"
            request = threading.Thread(target=lambda: urllib.request.urlopen(callback, timeout=2).read())
            request.start()
            code = receiver.wait(timeout=2)
            request.join(timeout=2)

        self.assertEqual(code, "auth-code")
        self.assertFalse(request.is_alive())

    def test_loopback_receiver_reports_provider_denial(self):
        flow = OAuthFlow.for_test(verifier="f" * 64, state="denied-state")
        with LoopbackReceiver(flow) as receiver:
            callback = (
                receiver.redirect_uri
                + "?state=denied-state&error=access_denied&error_description=User+cancelled"
            )

            def deny_request():
                try:
                    urllib.request.urlopen(callback, timeout=2).read()
                except urllib.error.HTTPError as error:
                    self.assertEqual(error.code, 400)
                    error.close()

            request = threading.Thread(target=deny_request)
            request.start()
            with self.assertRaisesRegex(OAuthError, "User cancelled"):
                receiver.wait(timeout=2)
            request.join(timeout=2)

        self.assertFalse(request.is_alive())

    def test_loopback_receiver_times_out_without_a_callback(self):
        flow = OAuthFlow.for_test(verifier="g" * 64, state="timeout-state")
        with LoopbackReceiver(flow) as receiver:
            with self.assertRaisesRegex(OAuthError, "timed out"):
                receiver.wait(timeout=0.01)

    def test_concurrent_loopback_receivers_avoid_callback_port_conflicts(self):
        first_flow = OAuthFlow.for_test(verifier="h" * 64, state="first-state")
        second_flow = OAuthFlow.for_test(verifier="i" * 64, state="second-state")
        with LoopbackReceiver(first_flow) as first, LoopbackReceiver(second_flow) as second:
            first_port = urlparse(first.redirect_uri).port
            second_port = urlparse(second.redirect_uri).port

        self.assertIsNotNone(first_port)
        self.assertIsNotNone(second_port)
        self.assertNotEqual(first_port, second_port)


if __name__ == "__main__":
    unittest.main()
