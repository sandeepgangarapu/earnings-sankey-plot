from __future__ import annotations

import io
import time
import unittest
from unittest.mock import patch

from earnings_sankey.sec import SECClient


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


if __name__ == "__main__":
    unittest.main()
