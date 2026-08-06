from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class SECError(RuntimeError):
    """Raised when SEC data cannot be retrieved or interpreted."""


@dataclass(frozen=True, slots=True)
class CompanyIdentity:
    ticker: str
    cik: int
    name: str


class SECClient:
    """Small, dependency-free client for the SEC's public JSON APIs.

    SEC asks automated clients to identify themselves with a company/person name
    and contact email. The client also spaces requests to stay comfortably below
    the SEC's published 10 requests/second ceiling.
    """

    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    _cache: dict[str, tuple[float, Any]] = {}
    _cache_lock = threading.Lock()

    def __init__(
        self,
        user_agent: str,
        *,
        timeout: float = 30.0,
        min_request_interval: float = 0.15,
        cache_seconds: float = 3600.0,
    ) -> None:
        user_agent = user_agent.strip()
        if not user_agent or "@" not in user_agent:
            raise ValueError(
                "SEC_USER_AGENT must identify you and include a contact email, "
                "for example 'Jane Doe jane@example.com'."
            )
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_request_interval = min_request_interval
        self.cache_seconds = cache_seconds
        self._last_request = 0.0
        self._request_lock = threading.Lock()

    def _get_json(self, url: str) -> Any:
        now = time.monotonic()
        with self._cache_lock:
            cached = self._cache.get(url)
            if cached and now - cached[0] < self.cache_seconds:
                return cached[1]

        with self._request_lock:
            delay = self.min_request_interval - (time.monotonic() - self._last_request)
            if delay > 0:
                time.sleep(delay)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    data = json.load(response)
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    raise SECError(f"SEC data was not found: {url}") from exc
                raise SECError(f"SEC returned HTTP {exc.code} for {url}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                raise SECError(f"Could not retrieve SEC data from {url}: {exc}") from exc
            finally:
                self._last_request = time.monotonic()

        with self._cache_lock:
            self._cache[url] = (time.monotonic(), data)
        return data

    def resolve_ticker(self, ticker: str) -> CompanyIdentity:
        ticker = ticker.strip().upper()
        if not ticker:
            raise ValueError("Ticker cannot be empty.")
        payload = self._get_json(self.TICKERS_URL)
        for item in payload.values():
            if str(item.get("ticker", "")).upper() == ticker:
                return CompanyIdentity(
                    ticker=ticker,
                    cik=int(item["cik_str"]),
                    name=str(item.get("title") or ticker),
                )
        raise SECError(f"Ticker {ticker!r} was not found in the SEC ticker list.")

    def companyfacts(self, ticker: str) -> tuple[CompanyIdentity, dict[str, Any]]:
        identity = self.resolve_ticker(ticker)
        payload = self._get_json(self.COMPANYFACTS_URL.format(cik=identity.cik))
        if not isinstance(payload, dict) or "facts" not in payload:
            raise SECError(f"SEC returned an unexpected Company Facts response for {ticker}.")
        return identity, payload


def filing_url(cik: int, accession: str | None) -> str | None:
    if not accession:
        return None
    compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{compact}/"
