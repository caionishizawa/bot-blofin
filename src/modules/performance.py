"""
Performance DB — SQLite-based trade history and performance metrics.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import aiosqlite

logger = logging.getLogger(__name__)


class PerformanceDB:
    """SQLite database for tracking trade performance."""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self._db = None

    async def initialize(self):
        """Create database and tables."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for better concurrent read access (web dashboard + bot)
        await self._db.execute("PRAGMA journal_mode=WAL")

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id                  TEXT PRIMARY KEY,
                pair                TEXT NOT NULL,
                direction           TEXT NOT NULL,
                entry               REAL NOT NULL,
                stop_loss           REAL NOT NULL,
                tp1                 REAL,
                tp2                 REAL,
                tp3                 REAL,
                risk_pct            REAL DEFAULT 2.0,
                rr_ratio            REAL DEFAULT 0.0,
                confidence          INTEGER DEFAULT 0,
                score               REAL DEFAULT 0.0,
                reasons             TEXT DEFAULT '[]',
                status              TEXT NOT NULL,
                exit_price          REAL,
                pnl_pct             REAL DEFAULT 0.0,
                opened_at           TEXT NOT NULL,
                closed_at           TEXT,
                duration_seconds    REAL,
                timeframe           TEXT DEFAULT '1H'
            )
        """)

        # Migrations for older schemas
        for col, definition in [
            ("rr_ratio",          "REAL DEFAULT 0.0"),
            ("duration_seconds",  "REAL"),
            ("timeframe",         "TEXT DEFAULT '1H'"),
        ]:
            try:
                await self._db.execute(f"ALTER TABLE trades ADD COLUMN {col} {definition}")
            except Exception:
                pass  # Column already exists

        await self._db.commit()
        logger.info(f"Database initialized: {self.db_path}")

    async def save_trade(self, trade: dict):
        """Insert or replace a trade record."""
        reasons = trade.get("reasons", [])
        if isinstance(reasons, list):
            reasons = json.dumps(reasons)

        trade_id = trade.get("id") or str(uuid.uuid4())

        await self._db.execute("""
            INSERT OR REPLACE INTO trades
            (id, pair, direction, entry, stop_loss, tp1, tp2, tp3,
             risk_pct, rr_ratio, confidence, score, reasons,
             status, exit_price, pnl_pct, opened_at, closed_at,
             duration_seconds, timeframe)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_id,
            trade["pair"],
            trade["direction"],
            trade["entry"],
            trade["stop_loss"],
            trade.get("tp1"),
            trade.get("tp2"),
            trade.get("tp3"),
            trade.get("risk_pct", 2.0),
            trade.get("rr_ratio", 0.0),
            trade.get("confidence", 0),
            trade.get("score", 0.0),
            reasons,
            trade["status"],
            trade.get("exit_price"),
            trade.get("pnl_pct", 0.0),
            trade.get("opened_at", datetime.now(timezone.utc).isoformat()),
            trade.get("closed_at"),
            trade.get("duration_seconds"),
            trade.get("timeframe", "1H"),
        ))
        await self._db.commit()
        return trade_id

    async def get_recent_trades(self, limit: int = 10) -> list:
        """Get most recent closed trades."""
        cursor = await self._db.execute(
            "SELECT * FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT ?",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_all_trades(self, limit: int = 100) -> list:
        """Get all trades ordered by opened_at DESC."""
        cursor = await self._db.execute(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_stats(self, days: int = 30) -> dict:
        """Calculate performance statistics for the given period."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = await self._db.execute(
            """SELECT pnl_pct, status, duration_seconds
               FROM trades
               WHERE closed_at >= ? AND closed_at IS NOT NULL""",
            (since,),
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
                "avg_duration_hours": 0.0,
            }

        pnl_list = [r[0] for r in rows]
        durations = [r[2] for r in rows if r[2] is not None]

        wins = sum(1 for p in pnl_list if p > 0)
        losses = sum(1 for p in pnl_list if p < 0)
        total = len(pnl_list)

        win_pnls = [p for p in pnl_list if p > 0]
        loss_pnls = [p for p in pnl_list if p < 0]

        gross_profit = sum(win_pnls) if win_pnls else 0.0
        gross_loss = abs(sum(loss_pnls)) if loss_pnls else 0.0

        if gross_loss > 0:
            profit_factor = round(gross_profit / gross_loss, 2)
        elif gross_profit > 0:
            profit_factor = 999.0  # All wins — display as high value
        else:
            profit_factor = 0.0

        # Max drawdown (peak-to-trough on cumulative PNL)
        running = 0.0
        peak = 0.0
        max_dd = 0.0
        for p in pnl_list:
            running += p
            peak = max(peak, running)
            max_dd = max(max_dd, peak - running)

        avg_duration_hours = round(sum(durations) / len(durations) / 3600, 1) if durations else 0.0

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / total) * 100, 1) if total > 0 else 0.0,
            "total_pnl": round(sum(pnl_list), 2),
            "max_drawdown": round(max_dd, 1),
            "profit_factor": profit_factor,
            "avg_win": round(sum(win_pnls) / len(win_pnls), 2) if win_pnls else 0.0,
            "avg_loss": round(sum(loss_pnls) / len(loss_pnls), 2) if loss_pnls else 0.0,
            "avg_duration_hours": avg_duration_hours,
        }

    async def get_daily_stats(self, days: int = 30) -> list:
        """Get daily aggregated stats for the last N days.

        Returns list of dicts: [{date, trades_count, wins, losses, pnl_sum}]
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self._db.execute(
            """SELECT
                   date(closed_at) AS trade_date,
                   COUNT(*)        AS trades_count,
                   SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN pnl_pct < 0 THEN 1 ELSE 0 END) AS losses,
                   ROUND(SUM(pnl_pct), 2) AS pnl_sum
               FROM trades
               WHERE closed_at >= ? AND closed_at IS NOT NULL
               GROUP BY date(closed_at)
               ORDER BY trade_date ASC""",
            (since,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_equity_curve(self, limit: int = 200) -> list:
        """Return chronological list of closed trades for equity curve."""
        cursor = await self._db.execute(
            """SELECT id, pair, direction, pnl_pct, closed_at, status
               FROM trades
               WHERE closed_at IS NOT NULL
               ORDER BY closed_at ASC
               LIMIT ?""",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_trades_today(self) -> int:
        """Return number of trades closed today."""
        today = datetime.now(timezone.utc).date().isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM trades WHERE date(closed_at) = ? AND closed_at IS NOT NULL",
            (today,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
