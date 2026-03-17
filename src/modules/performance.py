"""
Performance DB — SQLite-based trade history and performance metrics.
"""

import os
import json
import aiosqlite
from datetime import datetime, timedelta


class PerformanceDB:
    """SQLite database for tracking trade performance."""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self._db = None

    async def initialize(self):
        """Create database and tables."""
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                pair TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry REAL NOT NULL,
                stop_loss REAL NOT NULL,
                tp1 REAL,
                tp2 REAL,
                tp3 REAL,
                risk_pct REAL DEFAULT 2.0,
                status TEXT NOT NULL,
                exit_price REAL,
                pnl_pct REAL DEFAULT 0.0,
                confidence INTEGER DEFAULT 0,
                score REAL DEFAULT 0.0,
                reasons TEXT DEFAULT '[]',
                opened_at TEXT NOT NULL,
                closed_at TEXT
            )
        """)
        await self._db.commit()

    async def save_trade(self, trade: dict):
        """Insert or replace a trade record."""
        reasons = trade.get("reasons", [])
        if isinstance(reasons, list):
            reasons = json.dumps(reasons)

        await self._db.execute("""
            INSERT OR REPLACE INTO trades
            (id, pair, direction, entry, stop_loss, tp1, tp2, tp3,
             risk_pct, status, exit_price, pnl_pct, confidence, score, reasons, opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.get("id", ""),
            trade["pair"],
            trade["direction"],
            trade["entry"],
            trade["stop_loss"],
            trade.get("tp1"),
            trade.get("tp2"),
            trade.get("tp3"),
            trade.get("risk_pct", 2.0),
            trade["status"],
            trade.get("exit_price"),
            trade.get("pnl_pct", 0.0),
            trade.get("confidence", 0),
            trade.get("score", 0.0),
            reasons,
            trade.get("opened_at", datetime.utcnow().isoformat()),
            trade.get("closed_at"),
        ))
        await self._db.commit()

    async def get_recent_trades(self, limit: int = 10) -> list:
        """Get most recent trades."""
        cursor = await self._db.execute(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_stats(self, days: int = 30) -> dict:
        """Calculate performance statistics for the given period."""
        since = (datetime.utcnow() - timedelta(days=days)).isoformat()

        cursor = await self._db.execute(
            "SELECT pnl_pct, status FROM trades WHERE opened_at >= ?", (since,)
        )
        rows = await cursor.fetchall()

        if not rows:
            return {
                "total_trades": 0,
                "wins": 0,
                "losses": 0,
                "win_rate": 0.0,
                "total_pnl": 0.0,
                "max_drawdown": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
            }

        pnl_list = [r[0] for r in rows]
        wins = sum(1 for p in pnl_list if p > 0)
        losses = sum(1 for p in pnl_list if p <= 0)
        total = len(pnl_list)

        win_pnls = [p for p in pnl_list if p > 0]
        loss_pnls = [p for p in pnl_list if p < 0]

        gross_profit = sum(win_pnls) if win_pnls else 0.0
        gross_loss = abs(sum(loss_pnls)) if loss_pnls else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Max drawdown
        cumulative = []
        running = 0.0
        for p in pnl_list:
            running += p
            cumulative.append(running)

        peak = 0.0
        max_dd = 0.0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / total) * 100, 1) if total > 0 else 0.0,
            "total_pnl": round(sum(pnl_list), 2),
            "max_drawdown": round(max_dd, 1),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0.0,
            "avg_loss": round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.0,
        }

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
