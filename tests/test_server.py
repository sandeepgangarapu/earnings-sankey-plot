from __future__ import annotations

import http.client
import io
import json
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from http.server import ThreadingHTTPServer
from typing import Iterator
from unittest.mock import patch

from earnings_sankey import server as server_module


class _FakeSECClient:
    def __init__(self) -> None:
        self.requested_tickers: list[str] = []

    def company_directory(self) -> list[dict[str, str]]:
        return [
            {"ticker": "GOOGL", "name": "Alphabet Inc."},
            {"ticker": "AAPL", "name": "Apple Inc."},
        ]

    def companyfacts(self, ticker: str) -> tuple[object, dict[str, object]]:
        self.requested_tickers.append(ticker)
        return object(), {"facts": {}}


@contextmanager
def _running_server() -> Iterator[tuple[str, int]]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), server_module.AppHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _request(
    address: tuple[str, int],
    method: str,
    path: str,
    payload: dict[str, object] | None = None,
) -> tuple[int, object]:
    connection = http.client.HTTPConnection(*address, timeout=2)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    connection.request(method, path, body=body, headers=headers)
    response = connection.getresponse()
    response_body = json.loads(response.read())
    connection.close()
    return response.status, response_body


class ServerSECConfigurationTests(unittest.TestCase):
    def test_configured_client_uses_server_environment(self) -> None:
        client = server_module.configured_sec_client(
            {"SEC_USER_AGENT": "Web App web@example.com"}
        )

        self.assertEqual(client.user_agent, "Web App web@example.com")

    def test_configured_client_explains_missing_server_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "not configured for SEC access"):
            server_module.configured_sec_client({})


class ServerBrandingTests(unittest.TestCase):
    def test_help_presents_earnings_genie_as_the_product_name(self) -> None:
        self.assertIn("Run the Earnings Genie web app.", server_module.build_parser().format_help())

    def test_startup_message_presents_earnings_genie_as_the_product_name(self) -> None:
        output = io.StringIO()
        with patch.object(server_module, "ThreadingHTTPServer") as server_factory:
            server_factory.return_value.serve_forever.side_effect = KeyboardInterrupt
            with redirect_stdout(output):
                result = server_module.main(["--host", "127.0.0.1", "--port", "8765"])

        self.assertEqual(result, 0)
        self.assertEqual(
            output.getvalue().strip(),
            "Earnings Genie is running at http://127.0.0.1:8765",
        )


class ServerAPITests(unittest.TestCase):
    def test_company_directory_route_returns_compact_array(self) -> None:
        client = _FakeSECClient()
        with patch.object(server_module, "configured_sec_client", return_value=client):
            with _running_server() as address:
                status, payload = _request(address, "GET", "/api/companies")

        self.assertEqual(status, 200)
        self.assertEqual(payload, client.company_directory())

    def test_generate_uses_server_identity_and_simplified_payload(self) -> None:
        client = _FakeSECClient()
        normalized = object()
        with (
            patch.object(server_module, "configured_sec_client", return_value=client),
            patch.object(
                server_module,
                "available_periods",
                return_value=[{"fiscal_year": 2026, "period": "Q1"}],
            ),
            patch.object(server_module, "normalize_companyfacts", return_value=normalized),
            patch.object(server_module, "_result", return_value={"statement": {}, "svg": "<svg/>"}),
        ):
            with _running_server() as address:
                status, payload = _request(
                    address,
                    "POST",
                    "/api/generate",
                    {"ticker": "googl", "fiscal_year": 2026, "period": "Q1"},
                )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"statement": {}, "svg": "<svg/>"})
        self.assertEqual(client.requested_tickers, ["GOOGL"])


if __name__ == "__main__":
    unittest.main()
