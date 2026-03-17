"""
Test Phase 5+7: Tracker + Performance DB
Run: python tests/test_phase5_tracker_db.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from modules.tracker import ActiveTrade, TradeTracker, TradeStatus
from modules.performance import PerformanceDB


# ─── Tracker Unit Tests ─────────────────────────────────────

def test_active_trade_long():
    """Test LONG trade level detection."""
    trade = ActiveTrade({
        "pair": "BTC-USDT",
        "direction": "LONG",
        "entry": 100000,
        "stop_loss": 98000,
        "tp1": 103000,
        "tp2": 105000,
        "tp3": 108000,
        "risk_pct": 2.0,
    })

    # Test PNL calculation
    trade.current_price = 101000
    assert abs(trade.pnl_pct - 1.0) < 0.01, f"Expected ~1%, got {trade.pnl_pct}"

    # Test TP1 hit
    event = trade.check_levels(103500)
    assert event == "TP1_HIT", f"Expected TP1_HIT, got {event}"
    assert trade.tp1_hit is True

    # TP1 should not trigger again
    event = trade.check_levels(103600)
    assert event is None, "TP1 should not re-trigger"

    # Test TP2 hit
    event = trade.check_levels(105500)
    assert event == "TP2_HIT"

    # Test TP3 hit
    event = trade.check_levels(108500)
    assert event == "TP3_HIT"
    assert trade.status == TradeStatus.TP3_HIT

    print(f"  ✅ LONG trade: all levels detected correctly")


def test_active_trade_short():
    """Test SHORT trade level detection."""
    trade = ActiveTrade({
        "pair": "ETH-USDT",
        "direction": "SHORT",
        "entry": 4000,
        "stop_loss": 4100,
        "tp1": 3850,
        "tp2": 3750,
        "tp3": 3600,
        "risk_pct": 1.5,
    })

    # Negative PNL (price went up for short)
    trade.current_price = 4050
    assert trade.pnl_pct < 0, "Short PNL should be negative when price up"

    # Test SL hit
    event = trade.check_levels(4150)
    assert event == "SL_HIT"
    assert trade.status == TradeStatus.SL_HIT

    print(f"  ✅ SHORT trade: SL detection correct")


def test_trade_serialization():
    """Test trade to_dict()."""
    trade = ActiveTrade({
        "pair": "SOL-USDT",
        "direction": "LONG",
        "entry": 150,
        "stop_loss": 145,
        "tp1": 157,
        "tp2": 162,
        "tp3": 170,
    })

    d = trade.to_dict()
    assert d["pair"] == "SOL-USDT"
    assert d["direction"] == "LONG"
    assert d["entry"] == 150
    assert d["status"] == "open"
    assert "opened_at" in d

    print(f"  ✅ Trade serialization works")


# ─── Performance DB Tests ───────────────────────────────────

async def test_db_init():
    """Test database initialization."""
    db_path = "tests/output/test_trades.db"
    os.makedirs("tests/output", exist_ok=True)

    # Remove old test DB
    if os.path.exists(db_path):
        os.remove(db_path)

    db = PerformanceDB(db_path)
    await db.initialize()

    assert os.path.exists(db_path), "DB file should exist"
    print(f"  ✅ DB initialized at {db_path}")
    return db


async def test_db_save_and_query(db=None):
    """Test saving and querying trades."""
    if db is None:
        db = await test_db_init()

    # Save mock trades
    from datetime import datetime, timedelta

    trades = [
        {"id": "t1", "pair": "BTC-USDT", "direction": "LONG", "entry": 100000,
         "stop_loss": 98000, "tp1": 103000, "tp2": 105000, "tp3": 108000,
         "risk_pct": 2.0, "status": "tp2_hit", "exit_price": 105000,
         "pnl_pct": 5.0, "confidence": 75, "score": 4.5,
         "reasons": ["EMA cross", "RSI oversold"],
         "opened_at": (datetime.utcnow() - timedelta(days=2)).isoformat()},
        {"id": "t2", "pair": "ETH-USDT", "direction": "SHORT", "entry": 4000,
         "stop_loss": 4100, "tp1": 3850, "tp2": 3750, "tp3": 3600,
         "risk_pct": 1.5, "status": "sl_hit", "exit_price": 4100,
         "pnl_pct": -2.5, "confidence": 60, "score": 3.5,
         "reasons": ["MACD bearish"],
         "opened_at": (datetime.utcnow() - timedelta(days=1)).isoformat()},
        {"id": "t3", "pair": "SOL-USDT", "direction": "LONG", "entry": 150,
         "stop_loss": 145, "tp1": 157, "tp2": 162, "tp3": 170,
         "risk_pct": 2.0, "status": "tp3_hit", "exit_price": 170,
         "pnl_pct": 13.3, "confidence": 85, "score": 5.0,
         "reasons": ["Triple confluence"],
         "opened_at": datetime.utcnow().isoformat()},
    ]

    for t in trades:
        await db.save_trade(t)

    # Query recent
    recent = await db.get_recent_trades(limit=5)
    assert len(recent) == 3, f"Expected 3 trades, got {len(recent)}"
    print(f"  ✅ Saved & retrieved {len(recent)} trades")

    return db


async def test_db_stats(db=None):
    """Test performance statistics calculation."""
    if db is None:
        db = await test_db_save_and_query()

    stats = await db.get_stats(days=30)

    assert stats["total_trades"] == 3
    assert stats["wins"] == 2
    assert stats["losses"] == 1
    assert abs(stats["win_rate"] - 66.7) < 1, f"Win rate should be ~66.7%, got {stats['win_rate']}"
    assert stats["total_pnl"] > 0, "Total PNL should be positive"

    print(f"  ✅ Stats calculated:")
    print(f"     Trades: {stats['total_trades']}")
    print(f"     Win Rate: {stats['win_rate']:.1f}%")
    print(f"     Total PNL: {stats['total_pnl']:+.2f}%")
    print(f"     Max Drawdown: {stats['max_drawdown']:.1f}%")
    print(f"     Profit Factor: {stats['profit_factor']:.2f}")

    await db.close()
    return True


# ─── Run All ────────────────────────────────────────────────

async def run_all():
    print("\n🧪 PHASE 5+7 — Tracker + Performance Tests\n" + "=" * 40)

    # Sync tests
    sync_tests = [
        ("LONG Trade Levels", test_active_trade_long),
        ("SHORT Trade SL", test_active_trade_short),
        ("Trade Serialization", test_trade_serialization),
    ]

    passed = 0
    failed = 0

    for name, test_fn in sync_tests:
        try:
            print(f"\n📋 {name}...")
            test_fn()
            passed += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed += 1

    # Async tests
    async_tests = [
        ("DB Init", test_db_init),
        ("DB Save & Query", test_db_save_and_query),
        ("DB Stats", test_db_stats),
    ]

    for name, test_fn in async_tests:
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
