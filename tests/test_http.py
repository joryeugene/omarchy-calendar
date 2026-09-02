# SPDX-License-Identifier: GPL-3.0-or-later
import io
import json
import unittest
from email.message import Message

from omarchy_calendar import __version__
from omarchy_calendar.http import ReadOnlyHttp, ReadOnlyViolation


class FakeResponse:
    def __init__(self, payload, status=200, headers=None):
        self.payload = json.dumps(payload).encode()
        self.status = status
        self.headers = headers or Message()

    def read(self, amount=-1):
        return self.payload if amount < 0 else self.payload[:amount]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return FakeResponse(self.payload)


class ReadOnlyHttpTests(unittest.TestCase):
    def test_get_json_uses_get_and_returns_object(self):
        opener = FakeOpener({"value": [1]})
        http = ReadOnlyHttp(opener=opener)

        result = http.get_json("https://graph.microsoft.com/v1.0/me/calendars")

        self.assertEqual(result, {"value": [1]})
        self.assertEqual(opener.requests[0][0].get_method(), "GET")
        self.assertEqual(opener.requests[0][1], 20)
        self.assertEqual(
            opener.requests[0][0].get_header("User-agent"),
            f"omarchy-calendar/{__version__}",
        )

    def test_provider_transport_rejects_calendar_post(self):
        http = ReadOnlyHttp(opener=FakeOpener({}))

        with self.assertRaises(ReadOnlyViolation):
            http.request_json("POST", "https://graph.microsoft.com/v1.0/me/events", {"subject": "write"})
        with self.assertRaises(ReadOnlyViolation):
            http.request_json("DELETE", "https://www.googleapis.com/calendar/v3/calendars/a/events/b")

    def test_token_post_is_limited_to_known_oauth_hosts(self):
        opener = FakeOpener({"access_token": "token"})
        http = ReadOnlyHttp(opener=opener)

        result = http.post_token("https://oauth2.googleapis.com/token", {"grant_type": "authorization_code"})

        self.assertEqual(result["access_token"], "token")
        self.assertEqual(opener.requests[0][0].get_method(), "POST")
        with self.assertRaises(ReadOnlyViolation):
            http.post_token("https://example.com/token", {"grant_type": "authorization_code"})


if __name__ == "__main__":
    unittest.main()
