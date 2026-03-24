"""
BloFin API Wrapper — REST client with rate limiting and retry/backoff.
Credentials are loaded from environment variables.
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import os
import time
from typing import Optional

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BASE_URL  = "https://openapi.blofin.com"
logger    = logging.getLogger(__name__)

_MAX_RETRIES   = 4
_BACKOFF_BASE  = 1.5   # seconds — doubles each retry
_RATE_LIMIT_SLEEP = 0.25  # 250ms between consecutive requests (≤4 req/s)


def _sign(secret: str, timestamp: str, method: str, path: str, body: str = "") -> str:
    message = timestamp + method.upper() + path + body
    sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).digest()
    return base64.b64encode(sig).decode()


class BloFinAPI:
    """Async BloFin client with automatic retry and rate limiting."""

    def __init__(self, base_url: str = BASE_URL):
        self._base_url   = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._api_key    = os.getenv("BLOFIN_API_KEY", "")
        self._api_secret = os.getenv("BLOFIN_API_SECRET", "")
        self._passphrase = os.getenv("BLOFIN_API_PASSPHRASE", "")
        self._last_call  = 0.0   # timestamp of last request

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    def _auth_headers(self, method: str, path: str, body: str = "") -> dict:
        timestamp = str(int(time.time() * 1000))
        signature = _sign(self._api_secret, timestamp, method, path, body)
        return {
            "ACCESS-KEY":        self._api_key,
            "ACCESS-SIGN":       signature,
            "ACCESS-TIMESTAMP":  timestamp,
            "ACCESS-PASSPHRASE": self._passphrase,
            "Content-Type":      "application/json",
        }

    async def _throttle(self):
        """Ensure minimum gap between requests."""
        elapsed = time.monotonic() - self._last_call
        if elapsed < _RATE_LIMIT_SLEEP:
            await asyncio.sleep(_RATE_LIMIT_SLEEP - elapsed)
        self._last_call = time.monotonic()

    async def _request(
        self,
        method: str,
        path: str,
        params: dict = None,
        body: str = "",
        private: bool = False,
    ) -> dict:
        session = await self._get_session()
        url     = f"{self._base_url}{path}"
        headers = self._auth_headers(method, path, body) if private else {}

        for attempt in range(_MAX_RETRIES):
            await self._throttle()
            try:
                async with session.request(
                    method, url,
                    params=params,
                    data=body or None,
                    headers=headers,
                ) as resp:
                    if resp.status == 429:
                        wait = _BACKOFF_BASE ** (attempt + 2)
                        logger.warning("BloFin rate limited — waiting %.1fs", wait)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return await resp.json()

            except aiohttp.ClientResponseError as e:
                if e.status in (500, 502, 503, 504) and attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE ** (attempt + 1)
                    logger.warning("BloFin server error %d — retry in %.1fs", e.status, wait)
                    await asyncio.sleep(wait)
                    continue
                raise

            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
                if attempt < _MAX_RETRIES - 1:
                    wait = _BACKOFF_BASE ** (attempt + 1)
                    logger.warning("BloFin connection error — retry in %.1fs: %s", wait, e)
                    await asyncio.sleep(wait)
                    continue
                raise

        raise RuntimeError(f"BloFin API: max retries exceeded for {method} {path}")

    # ------------------------------------------------------------------
    # Public endpoints
    # ------------------------------------------------------------------

    async def get_ticker(self, pair: str) -> dict:
        data    = await self._request("GET", "/api/v1/market/tickers", params={"instId": pair})
        tickers = data.get("data", [])
        return tickers[0] if tickers else {}

    async def get_candles(self, pair: str, bar: str = "1H", limit: int = 100) -> list:
        params  = {"instId": pair, "bar": bar, "limit": str(limit)}
        data    = await self._request("GET", "/api/v1/market/candles", params=params)
        candles = data.get("data", [])
        candles.reverse()
        return candles

    async def get_orderbook(self, pair: str, depth: int = 10) -> dict:
        params = {"instId": pair, "sz": str(depth)}
        data   = await self._request("GET", "/api/v1/market/books", params=params)
        books  = data.get("data", [])
        return books[0] if books else {"asks": [], "bids": []}

    async def get_mark_price(self, pair: str) -> float:
        """Retorna preço atual do par. Tenta mark-price, fallback para last ticker."""
        try:
            data  = await self._request("GET", "/api/v1/market/mark-price", params={"instId": pair})
            items = data.get("data", [])
            if items and float(items[0].get("markPrice", 0)) > 0:
                return float(items[0]["markPrice"])
        except Exception:
            pass
        # Fallback: last price from ticker
        try:
            ticker = await self.get_ticker(pair)
            last = float(ticker.get("last", 0))
            if last > 0:
                return last
        except Exception:
            pass
        return 0.0

    async def get_all_mark_prices(self) -> dict:
        """Retorna dict {pair: price} para todos os pares ativos."""
        # Tenta endpoint de mark-price em batch
        try:
            data  = await self._request("GET", "/api/v1/market/mark-price", params={"instType": "SWAP"})
            items = data.get("data", [])
            result = {
                item["instId"]: float(item.get("markPrice", 0))
                for item in items
                if item.get("instId") and float(item.get("markPrice", 0)) > 0
            }
            if result:
                return result
        except Exception as e:
            logger.warning(f"Batch mark-price falhou: {e}")
        # Fallback: tickers individuais via tickers endpoint
        try:
            data  = await self._request("GET", "/api/v1/market/tickers", params={"instType": "SWAP"})
            items = data.get("data", [])
            return {
                item["instId"]: float(item.get("last", 0))
                for item in items
                if item.get("instId") and float(item.get("last", 0)) > 0
            }
        except Exception as e:
            logger.warning(f"Batch tickers falhou: {e}")
        return {}

    async def get_multi_tickers(self, pairs: list) -> dict:
        result  = {}
        tasks   = [self.get_ticker(pair) for pair in pairs]
        tickers = await asyncio.gather(*tasks, return_exceptions=True)
        for pair, ticker in zip(pairs, tickers):
            if not isinstance(ticker, Exception):
                result[pair] = ticker
        return result

    # ------------------------------------------------------------------
    # Private endpoints
    # ------------------------------------------------------------------

    async def get_balance(self, currency: str = "USDT") -> dict:
        data = await self._request("GET", "/api/v1/asset/balances",
                                   params={"currency": currency}, private=True)
        return data.get("data", {})

    async def get_positions(self, inst_type: str = "SWAP") -> list:
        data = await self._request("GET", "/api/v1/account/positions",
                                   params={"instType": inst_type}, private=True)
        return data.get("data", [])

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
