from __future__ import annotations

import argparse
import json
import mimetypes
import os
import webbrowser
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from .cli import SAMPLE_PATH, _load_json
from .models import Statement
from .normalize import available_periods, normalize_companyfacts
from .render import render_svg
from .sec import SECClient


WEB_ROOT = Path(__file__).resolve().parents[2] / "web"


def configured_sec_client(environ: Mapping[str, str] | None = None) -> SECClient:
    environment = os.environ if environ is None else environ
    user_agent = str(environment.get("SEC_USER_AGENT") or "").strip()
    if not user_agent:
        raise ValueError(
            "This service is not configured for SEC access. Set SEC_USER_AGENT "
            "on the server to a name and contact email."
        )
    return SECClient(user_agent)


def _result(statement: Statement) -> dict[str, Any]:
    return {
        "statement": statement.to_dict(),
        "svg": render_svg(statement),
    }


class AppHandler(BaseHTTPRequestHandler):
    server_version = "EarningsSankey/0.1"

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_file(self, path: Path) -> None:
        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        route = urlparse(self.path).path
        if route == "/api/companies":
            try:
                self._json(HTTPStatus.OK, configured_sec_client().company_directory())
            except (OSError, ValueError, RuntimeError) as exc:
                self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        if route == "/api/sample":
            try:
                self._json(HTTPStatus.OK, _result(Statement.from_dict(_load_json(SAMPLE_PATH))))
            except (OSError, ValueError) as exc:
                self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})
            return
        if route == "/healthz":
            self._json(HTTPStatus.OK, {"ok": True})
            return
        relative = "index.html" if route == "/" else unquote(route.lstrip("/"))
        candidate = (WEB_ROOT / relative).resolve()
        if WEB_ROOT.resolve() not in candidate.parents and candidate != WEB_ROOT.resolve():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        self._serve_file(candidate)

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/generate":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0 or content_length > 1_000_000:
                raise ValueError("Request body must be between 1 byte and 1 MB.")
            payload = json.loads(self.rfile.read(content_length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a JSON object.")
            ticker = str(payload.get("ticker", "")).strip().upper()
            client = configured_sec_client()
            identity, companyfacts = client.companyfacts(ticker)
            fiscal_year = payload.get("fiscal_year")
            period = str(payload.get("period") or "").upper() or None
            periods = available_periods(companyfacts)
            matching = [
                item
                for item in periods
                if (fiscal_year is None or item["fiscal_year"] == int(fiscal_year))
                and (period is None or item["period"] == period)
            ]
            if not matching:
                raise ValueError("No matching SEC fiscal period was found.")
            selected = matching[0]
            statement = normalize_companyfacts(
                companyfacts,
                identity,
                selected["fiscal_year"],
                selected["period"],
            )
            self._json(HTTPStatus.OK, _result(statement))
        except (json.JSONDecodeError, OSError, ValueError, RuntimeError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        # Keep the standard concise access log; request bodies and SEC identity are never logged.
        super().log_message(format, *args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Earnings Genie web app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--open", action="store_true", help="Open the app in a browser.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    address = (args.host, args.port)
    server = ThreadingHTTPServer(address, AppHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Earnings Genie is running at {url}")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
