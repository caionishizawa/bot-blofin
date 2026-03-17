"""
Test Phase 2: Scanner + Indicators
Run: python tests/test_phase2_scanner.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.blofin_api import BloFinAPI
from utils.indicators import candles_to_df, add_all_indicators, detect_signal


async def test_candles_to_df():
    """Test converting BloFin candles to DataFrame."""
    api = BloFinAPI()
    candles = await api.get_candles("BTC-USDT", bar="1H", limit=200)
    await api.close()

    df = candles_to_df(candles)
    assert not df.empty, "DataFrame should not be empty"
    assert "open" in df.columns, "Should have OHLCV columns"
    assert "close" in df.columns
    assert "datetime" in df.columns
    assert len(df) >= 100, f"Expected 100+ rows, got {len(df)}"
    print(f"  ✅ DataFrame: {len(df)} rows, {len(df.columns)} columns")
    return df


async def test_indicators(df=None):
    """Test adding all indicators."""
    if df is None:
        df = await test_candles_to_df()

    df = add_all_indicators(df)

    required_indicators = ["ema9", "ema21", "rsi", "macd", "bb_upper", "bb_lower", "atr", "adx"]
    for ind in required_indicators:
        assert ind in df.columns, f"Missing indicator: {ind}"
        assert df[ind].notna().sum() > 0, f"Indicator {ind} is all NaN"

    last = df.iloc[-1]
    print(f"  ✅ Indicators calculated:")
    print(f"     RSI: {last['rsi']:.1f}")
    print(f"     MACD: {last['macd']:.4f}")
    print(f"     EMA9: {last['ema9']:.2f}")
    print(f"     ADX: {last['adx']:.1f}")
    print(f"     BB Width: {last['bb_width']:.4f}")
    return df


async def test_signal_detection(df=None):
    """Test signal detection logic."""
    if df is None:
        df = await test_indicators()

    signal = detect_signal(df)

    if signal:
        print(f"  ✅ Signal detected:")
        print(f"     Direction: {signal['direction']}")
        print(f"     Entry: {signal['entry']}")
        print(f"     SL: {signal['stop_loss']}")
        print(f"     TP1/TP2/TP3: {signal['tp1']}/{signal['tp2']}/{signal['tp3']}")
        print(f"     Score: {signal['score']}/6")
        print(f"     Confidence: {signal['confidence']}%")
        print(f"     R:R: {signal['rr_ratio']}:1")
        print(f"     Reasons: {len(signal['reasons'])}")
        for r in signal['reasons']:
            print(f"       • {r}")

        # Validate signal structure
        assert signal["entry"] > 0
        assert signal["stop_loss"] > 0
        assert signal["rr_ratio"] >= 1.0
        assert 0 <= signal["confidence"] <= 100
    else:
        print(f"  ⚠️ No signal found (this is normal — means no confluence)")

    return signal


async def test_multi_pair_scan():
    """Test scanning multiple pairs."""
    api = BloFinAPI()
    pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
    signals = []

    for pair in pairs:
        candles = await api.get_candles(pair, bar="1H", limit=200)
        if candles:
            df = candles_to_df(candles)
            df = add_all_indicators(df)
            signal = detect_signal(df)
            if signal:
                signal["pair"] = pair
                signals.append(signal)
        await asyncio.sleep(0.3)

    await api.close()

    print(f"  ✅ Scanned {len(pairs)} pairs, found {len(signals)} signals")
    for s in signals:
        print(f"     {s['pair']}: {s['direction']} (score: {s['score']})")

    return True


async def run_all():
    print("\n🧪 PHASE 2 — Scanner + Indicators Tests\n" + "=" * 40)

    tests = [
        ("Candles → DataFrame", test_candles_to_df),
        ("Add Indicators", test_indicators),
        ("Signal Detection", test_signal_detection),
        ("Multi-Pair Scan", test_multi_pair_scan),
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
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'✅ ALL PASSED' if failed == 0 else '❌ SOME FAILED'}")
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all())
    sys.exit(0 if success else 1)
