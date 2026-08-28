# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from omarchy_calendar.normalize import extract_meeting_url, plain_text


class NormalizeTests(unittest.TestCase):
    def test_plain_text_removes_markup_decodes_entities_and_limits_length(self):
        source = "<p>Hello&nbsp;<b>calendar</b></p>" + ("x" * 5000)
        result = plain_text(source)
        self.assertTrue(result.startswith("Hello calendar"))
        self.assertNotIn("<b>", result)
        self.assertLessEqual(len(result), 4000)

    def test_meeting_extraction_accepts_known_https_hosts_only(self):
        text = "Join https://zoom.us/j/123?pwd=abc or see https://example.com/not-a-meeting"
        self.assertEqual(extract_meeting_url(text), "https://zoom.us/j/123?pwd=abc")
        self.assertEqual(extract_meeting_url("javascript:alert(1)"), "")
        self.assertEqual(extract_meeting_url("http://meet.google.com/insecure"), "")


if __name__ == "__main__":
    unittest.main()
