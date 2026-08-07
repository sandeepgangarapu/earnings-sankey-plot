from __future__ import annotations

import io
import time
import unittest
from unittest.mock import patch

from earnings_sankey.sec import SECClient, SECError


class _JSONResponse(io.BytesIO):
    def __enter__(self) -> "_JSONResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class SECClientPacingTests(unittest.TestCase):
    def setUp(self) -> None:
        SECClient._cache = {}
        SECClient._last_request = 0.0

    def test_separate_clients_share_request_pacing(self) -> None:
        upstream_starts: list[float] = []

        def open_upstream(*args: object, **kwargs: object) -> _JSONResponse:
            upstream_starts.append(time.monotonic())
            return _JSONResponse(b"{}")

        first = SECClient("First User first@example.com", min_request_interval=0.05)
        second = SECClient("Second User second@example.com", min_request_interval=0.05)

        with patch("earnings_sankey.sec.urllib.request.urlopen", side_effect=open_upstream):
            first._get_json("https://example.test/first")
            second._get_json("https://example.test/second")

        self.assertEqual(len(upstream_starts), 2)
        self.assertGreaterEqual(upstream_starts[1] - upstream_starts[0], 0.04)


class SECCompanyDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = SECClient("Test User test@example.com")

    def test_company_directory_returns_only_browser_search_fields(self) -> None:
        payload = {
            "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
            "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
            "2": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
        }

        with patch.object(self.client, "_get_json", return_value=payload):
            self.assertEqual(
                self.client.company_directory(),
                [
                    {"ticker": "AAPL", "name": "Apple Inc."},
                    {"ticker": "GOOGL", "name": "Alphabet Inc."},
                    {"ticker": "MSFT", "name": "MICROSOFT CORP"},
                ],
            )

    def test_company_directory_skips_incomplete_entries(self) -> None:
        payload = {
            "0": {"cik_str": 1, "ticker": "GOOD", "title": "Good Company"},
            "1": {"cik_str": 2, "ticker": "", "title": "Missing Ticker"},
            "2": {"cik_str": 3, "ticker": "NONAME", "title": ""},
            "3": "not an object",
        }

        with patch.object(self.client, "_get_json", return_value=payload):
            self.assertEqual(
                self.client.company_directory(),
                [{"ticker": "GOOD", "name": "Good Company"}],
            )

    def test_company_directory_rejects_an_unexpected_response(self) -> None:
        with patch.object(self.client, "_get_json", return_value=[]):
            with self.assertRaisesRegex(SECError, "unexpected company ticker response"):
                self.client.company_directory()


if __name__ == "__main__":
    unittest.main()
