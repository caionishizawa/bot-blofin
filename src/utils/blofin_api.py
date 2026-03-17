"""
BloFin API Wrapper — REST client for public market data.
"""

import asyncio
import aiohttp
from typing import Optional


BASE_URL = "https://openapi.blofin.com"


class BloFinAPI:
    """Async client for BloFin public API endpoints."""

    def __init__(self, base_url: str = BASE_URL):
        self._base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _request(self, method: str, path: str, params: dict = None) -> dict:
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        async with session.request(method, url, params=params) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data

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

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()
