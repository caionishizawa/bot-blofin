"""
Test Phase 1: Foundation — BloFin API Wrapper
Run: python -m pytest tests/test_phase1_api.py -v
Or:  python tests/test_phase1_api.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.blofin_api import BloFinAPI
from conftest import requires_network


@requires_network
async def test_get_ticker():
    """Test fetching BTC-USDT ticker."""
    api = BloFinAPI()
    ticker = await api.get_ticker("BTC-USDT")
    await api.close()

    assert ticker, "Ticker should not be empty"
    assert "last" in ticker, "Ticker should have 'last' price"
    price = float(ticker["last"])
    assert price > 0, f"Price should be positive, got {price}"
    print(f"  ✅ BTC-USDT price: ${price:,.2f}")
    return True


@requires_network
async def test_get_candles():
    """Test fetching candlestick data."""
    api = BloFinAPI()
    candles = await api.get_candles("BTC-USDT", bar="1H", limit=100)
    await api.close()

    assert candles, "Candles should not be empty"
    assert len(candles) >= 50, f"Expected 50+ candles, got {len(candles)}"
    # Each candle should have OHLCV
    first = candles[0]
    assert len(first) >= 5, f"Candle should have 5+ fields, got {len(first)}"
    print(f"  ✅ Got {len(candles)} candles")
    return True


@requires_network
async def test_get_orderbook():
    """Test fetching order book."""
    api = BloFinAPI()
    book = await api.get_orderbook("BTC-USDT", depth=10)
    await api.close()

    assert "asks" in book or "bids" in book, "Orderbook should have asks/bids"
    print(f"  ✅ Orderbook: {len(book.get('asks', []))} asks, {len(book.get('bids', []))} bids")
    return True


@requires_network
async def test_get_mark_price():
    """Test fetching mark price."""
    api = BloFinAPI()
    price = await api.get_mark_price("BTC-USDT")
    await api.close()

    assert price > 0, f"Mark price should be positive, got {price}"
    print(f"  ✅ Mark price: ${price:,.2f}")
    return True


@requires_network
async def test_multi_tickers():
    """Test fetching multiple tickers."""
    api = BloFinAPI()
    pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    tickers = await api.get_multi_tickers(pairs)
    await api.close()

    assert len(tickers) == len(pairs), f"Should get {len(pairs)} tickers"
    for pair in pairs:
        assert pair in tickers, f"Missing ticker for {pair}"
    print(f"  ✅ Got tickers for {list(tickers.keys())}")
    return True


async def run_all():
    print("\n🧪 PHASE 1 — BloFin API Tests\n" + "=" * 40)

    tests = [
        ("GET Ticker", test_get_ticker),
        ("GET Candles", test_get_candles),
        ("GET Orderbook", test_get_orderbook),
        ("GET Mark Price", test_get_mark_price),
        ("Multi Tickers", test_multi_tickers),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            print(f"\n📋 {name}...")
            result = await test_fn()
            if result:
                passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'✅ ALL PASSED' if failed == 0 else '❌ SOME FAILED'}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
