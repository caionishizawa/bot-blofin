"""
BloFin API Wrapper — REST client for public and private endpoints.
Credentials are loaded from environment variables (BLOFIN_API_KEY / BLOFIN_API_SECRET).
"""

import asyncio
import base64
import hashlib
import hmac
import os
import time
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://openapi.blofin.com"


def _sign(secret: str, timestamp: str, method: str, path: str, body: str = "") -> str:
    """Return base64-encoded HMAC-SHA256 signature."""
    message = timestamp + method.upper() + path + body
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


class BloFinAPI:
    """Async client for BloFin API (public + private endpoints)."""

    def __init__(self, base_url: str = BASE_URL):
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._api_key: str = os.getenv("BLOFIN_API_KEY", "")
        self._api_secret: str = os.getenv("BLOFIN_API_SECRET", "")
        self._passphrase: str = os.getenv("BLOFIN_API_PASSPHRASE", "")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        """Build authentication headers for private endpoints."""
        timestamp = str(int(time.time() * 1000))
        signature = _sign(self._api_secret, timestamp, method, path, body)
        return {
            "ACCESS-KEY": self._api_key,
            "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp,
            "ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        body: str = "",
        private: bool = False,
    ) -> dict:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        headers = self._auth_headers(method, path, body) if private else {}
        async with session.request(
            method, url, params=params, data=body or None, headers=headers
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    async def get_ticker(self, pair: str) -> dict:
        """Fetch ticker for a single trading pair."""
        data = await self._request("GET", "/api/v1/market/tickers", params={"instId": pair})
        tickers = data.get("data", [])
        if not tickers:
            return {}
        return tickers[0]

    async def get_candles(self, pair: str, bar: str = "1H", limit: int = 100) -> list:
        """Fetch OHLCV candlestick data.

        Returns list of lists: [ts, open, high, low, close, vol, ...]
        """
        params = {"instId": pair, "bar": bar, "limit": str(limit)}
        data = await self._request("GET", "/api/v1/market/candles", params=params)
        candles = data.get("data", [])
        # API returns newest first — reverse to chronological order
        candles.reverse()
        return candles

    async def get_orderbook(self, pair: str, depth: int = 10) -> dict:
        """Fetch order book."""
        params = {"instId": pair, "sz": str(depth)}
        data = await self._request("GET", "/api/v1/market/books", params=params)
        books = data.get("data", [])
        if not books:
            return {"asks": [], "bids": []}
        return books[0]

    async def get_mark_price(self, pair: str) -> float:
        """Fetch mark price for a pair."""
        data = await self._request("GET", "/api/v1/market/mark-price", params={"instId": pair})
        items = data.get("data", [])
        if not items:
            return 0.0
        return float(items[0].get("markPrice", 0))

    async def get_multi_tickers(self, pairs: list) -> dict:
        """Fetch tickers for multiple pairs."""
        result = {}
        tasks = [self.get_ticker(pair) for pair in pairs]
        tickers = await asyncio.gather(*tasks, return_exceptions=True)
        for pair, ticker in zip(pairs, tickers):
            if isinstance(ticker, Exception):
                continue
            result[pair] = ticker
        return result

    # ------------------------------------------------------------------
    # Private endpoints (require API key + secret)
    # ------------------------------------------------------------------

    async def get_balance(self, currency: str = "USDT") -> dict:
        """Fetch account balance for a currency."""
        path = "/api/v1/asset/balances"
        data = await self._request("GET", path, params={"currency": currency}, private=True)
        return data.get("data", {})

    async def get_positions(self, inst_type: str = "SWAP") -> list:
        """Fetch open positions."""
        path = "/api/v1/account/positions"
        data = await self._request("GET", path, params={"instType": inst_type}, private=True)
        return data.get("data", [])

    # ------------------------------------------------------------------

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
