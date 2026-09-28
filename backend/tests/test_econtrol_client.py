"""Tests for the authenticated public E-Control request boundary."""

import io
import json
import unittest
from unittest.mock import patch

from app.econtrol_client import fetch_nearby
from scripts.check_econtrol_access import shape


class EControlClientTests(unittest.TestCase):
    def test_documented_endpoint_and_required_headers(self):
        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 20)
            self.assertIn("/charge/1.0/search?latitude=48.2&longitude=16.3", request.full_url)
            self.assertEqual(request.get_header("Apikey"), "test-key")
            self.assertEqual(request.get_header("Referer"), "https://example.org")
            return io.BytesIO(json.dumps({"stations": []}).encode())

        with patch("app.econtrol_client.urlopen", side_effect=fake_urlopen):
            self.assertEqual(
                fetch_nearby(48.2, 16.3, api_key="test-key", referer="https://example.org"),
                {"stations": []},
            )

    def test_rejects_missing_credentials_and_invalid_coordinates(self):
        with self.assertRaises(ValueError):
            fetch_nearby(100, 16, api_key="test", referer="https://example.org")
        with self.assertRaises(ValueError):
            fetch_nearby(48, 16, api_key="", referer="https://example.org")
        with self.assertRaises(ValueError):
            fetch_nearby(48, 16, api_key="test", referer="http://example.org")

    def test_shape_omits_values(self):
        result = shape({"secret": "private-value", "items": [{"id": "123"}]})
        self.assertNotIn("private-value", result)
        self.assertNotIn("123", result)


if __name__ == "__main__":
    unittest.main()
