"""
Test Phase 3: Chart Generator
Run: python tests/test_phase3_charts.py

Generates a test chart PNG to verify visual output.
"""

import asyncio
import sys
import os
import time

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.indicators import candles_to_df, add_all_indicators, detect_signal
from modules.chart_generator import create_chart, create_pnl_chart


def generate_mock_candles(n=200, base_price=90000.0):
    """Generate synthetic BTC-like OHLCV candles."""
    candles = []
    price = base_price
    ts = int(time.time() * 1000) - n * 3600000
    for i in range(n):
        change = np.random.normal(0, 0.008) * price
        open_ = price
        close = price + change
        high = max(open_, close) * (1 + abs(np.random.normal(0, 0.003)))
        low = min(open_, close) * (1 - abs(np.random.normal(0, 0.003)))
        vol = np.random.uniform(100, 1000)
        candles.append([str(ts), str(open_), str(high), str(low), str(close), str(vol)])
        price = close
        ts += 3600000
    return candles


TEST_CONFIG = {
    "chart": {
        "style": "dark",
        "watermark": "🤖 @TestChannel",
        "width": 1200,
        "height": 800,
        "candles": 80,
        "timeframe": "1H",
    }
}


async def test_signal_chart():
    """Test generating a signal chart."""
    candles = generate_mock_candles(n=200, base_price=90000.0)

    df = candles_to_df(candles)
    df = add_all_indicators(df)

    # Create a signal (use detect or mock)
    signal = detect_signal(df)
    if not signal:
        # Mock signal if no real one detected
        last = df.iloc[-1]
        signal = {
            "pair": "BTC-USDT",
            "direction": "LONG",
            "entry": float(last["close"]),
            "stop_loss": float(last["close"] * 0.98),
            "tp1": float(last["close"] * 1.03),
            "tp2": float(last["close"] * 1.05),
            "tp3": float(last["close"] * 1.08),
            "score": 4.0,
            "confidence": 67,
            "rr_ratio": 2.5,
            "timeframe": "1H",
            "candles_df": df,
        }
    else:
        signal["candles_df"] = df

    buf = create_chart(signal, TEST_CONFIG)
    assert buf is not None, "Chart buffer should not be None"
    assert buf.getbuffer().nbytes > 10000, "Chart should be > 10KB"

    # Save to file for visual inspection
    os.makedirs("tests/output", exist_ok=True)
    with open("tests/output/test_signal_chart.png", "wb") as f:
        f.write(buf.getvalue())

    size_kb = buf.getbuffer().nbytes / 1024
    print(f"  ✅ Signal chart generated: {size_kb:.0f} KB")
    print(f"     Saved to: tests/output/test_signal_chart.png")
    return True


async def test_pnl_chart():
    """Test generating a PNL equity curve chart."""
    # Mock trade history
    mock_trades = [
        {"pnl_pct": 2.1},
        {"pnl_pct": -1.0},
        {"pnl_pct": 3.5},
        {"pnl_pct": 1.2},
        {"pnl_pct": -0.8},
        {"pnl_pct": 4.0},
        {"pnl_pct": -1.5},
        {"pnl_pct": 2.0},
        {"pnl_pct": 1.8},
        {"pnl_pct": -0.5},
        {"pnl_pct": 3.0},
        {"pnl_pct": -2.0},
        {"pnl_pct": 1.5},
        {"pnl_pct": 2.5},
        {"pnl_pct": -0.3},
    ]

    buf = create_pnl_chart(mock_trades, TEST_CONFIG)
    assert buf is not None
    assert buf.getbuffer().nbytes > 5000

    os.makedirs("tests/output", exist_ok=True)
    with open("tests/output/test_pnl_chart.png", "wb") as f:
        f.write(buf.getvalue())

    size_kb = buf.getbuffer().nbytes / 1024
    print(f"  ✅ PNL chart generated: {size_kb:.0f} KB")
    print(f"     Saved to: tests/output/test_pnl_chart.png")
    return True


async def run_all():
    print("\n🧪 PHASE 3 — Chart Generator Tests\n" + "=" * 40)

    tests = [
        ("Signal Chart", test_signal_chart),
        ("PNL Chart", test_pnl_chart),
    ]

    passed = 0
    failed = 0

    for name, test_fn in tests:
        try:
            print(f"\n📋 {name}...")
            await test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
