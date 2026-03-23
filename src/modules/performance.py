"""
Performance DB — SQLite-based trade history and performance metrics.
"""

import os
import json
import uuid
import aiosqlite
from datetime import datetime, timedelta, timezone


class PerformanceDB:
    """SQLite database for tracking trade performance."""

    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = db_path
        self._db = None

    async def initialize(self):
        """Create database and tables."""
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id          TEXT PRIMARY KEY,
                pair        TEXT NOT NULL,
                direction   TEXT NOT NULL,
                entry       REAL NOT NULL,
                stop_loss   REAL NOT NULL,
                tp1         REAL,
                tp2         REAL,
                tp3         REAL,
                risk_pct    REAL DEFAULT 2.0,
                rr_ratio    REAL DEFAULT 0.0,
                confidence  INTEGER DEFAULT 0,
                score       REAL DEFAULT 0.0,
                reasons     TEXT DEFAULT '[]',
                status      TEXT NOT NULL,
                exit_price  REAL,
                pnl_pct     REAL DEFAULT 0.0,
                pnl_usd     REAL DEFAULT 0.0,
                tp1_hit     INTEGER DEFAULT 0,
                tp2_hit     INTEGER DEFAULT 0,
                tp3_hit     INTEGER DEFAULT 0,
                sl_hit      INTEGER DEFAULT 0,
                opened_at   TEXT NOT NULL,
                closed_at   TEXT
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS groups (
                chat_id   TEXT PRIMARY KEY,
                title     TEXT,
                enabled   INTEGER DEFAULT 1,
                added_at  TEXT NOT NULL
            )
        """)
        # Migrations for older schemas
        for col, definition in [
            ("rr_ratio", "REAL DEFAULT 0.0"),
            ("pnl_usd",  "REAL DEFAULT 0.0"),
            ("tp1_hit",  "INTEGER DEFAULT 0"),
            ("tp2_hit",  "INTEGER DEFAULT 0"),
            ("tp3_hit",  "INTEGER DEFAULT 0"),
            ("sl_hit",   "INTEGER DEFAULT 0"),
        ]:
            try:
                await self._db.execute(f"ALTER TABLE trades ADD COLUMN {col} {definition}")
            except Exception:
                pass
        await self._db.commit()

    async def enable_group(self, chat_id: str, title: str = ""):
        """Register or re-enable a group for signal broadcasting."""
        await self._db.execute("""
            INSERT INTO groups (chat_id, title, enabled, added_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled=1, title=excluded.title
        """, (str(chat_id), title, datetime.now(timezone.utc).isoformat()))
        await self._db.commit()

    async def disable_group(self, chat_id: str):
        """Disable signal broadcasting for a group."""
        await self._db.execute(
            "UPDATE groups SET enabled=0 WHERE chat_id=?", (str(chat_id),)
        )
        await self._db.commit()

    async def get_enabled_groups(self) -> list:
        """Return list of dicts for all enabled groups."""
        cursor = await self._db.execute(
            "SELECT chat_id, title FROM groups WHERE enabled=1"
        )
        rows = await cursor.fetchall()
        return [{"chat_id": r[0], "title": r[1]} for r in rows]

    async def list_groups(self) -> list:
        """Return all registered groups with their status."""
        cursor = await self._db.execute(
            "SELECT chat_id, title, enabled FROM groups ORDER BY added_at DESC"
        )
        rows = await cursor.fetchall()
        return [{"chat_id": r[0], "title": r[1], "enabled": bool(r[2])} for r in rows]

    @staticmethod
    def calc_pnl_usd(trade: dict, bankroll: float) -> float:
        """Calcula PNL em USD considerando fechamentos parciais por TP level.

        Modelo de risco fixo:
          • Cada trade arrisca `risk_pct`% da banca (ex: 2% de $1000 = $20)
          • TP1 fecha 30% da posição, TP2 40%, TP3 30%
          • SL fecha o restante em perda total do valor arriscado
        """
        risk_pct = trade.get("risk_pct", 2.0)
        risk_amount = bankroll * risk_pct / 100

        entry     = trade.get("entry", 0)
        stop_loss = trade.get("stop_loss", 0)
        tp1       = trade.get("tp1", 0)
        tp2       = trade.get("tp2", 0)
        tp3       = trade.get("tp3", 0)

        if not entry or not stop_loss:
            return 0.0
        sl_dist = abs(entry - stop_loss)
        if sl_dist == 0:
            return 0.0

        tp1_hit = bool(trade.get("tp1_hit", False))
        tp2_hit = bool(trade.get("tp2_hit", False))
        tp3_hit = bool(trade.get("tp3_hit", False))
        sl_hit  = bool(trade.get("sl_hit",  False))

        # TP sizing: TP1=50%, TP2=30%, TP3=20%
        pnl = 0.0
        if tp1_hit and tp1:
            pnl += risk_amount * (abs(tp1 - entry) / sl_dist) * 0.50
        if tp2_hit and tp2:
            pnl += risk_amount * (abs(tp2 - entry) / sl_dist) * 0.30
        if tp3_hit and tp3:
            pnl += risk_amount * (abs(tp3 - entry) / sl_dist) * 0.20
        if sl_hit:
            remaining = 1.0 - (0.50 if tp1_hit else 0) - (0.30 if tp2_hit else 0)
            pnl -= risk_amount * remaining

        return round(pnl, 2)

    async def save_trade(self, trade: dict, bankroll: float = 1000.0):
        """Insert or replace a trade record."""
        reasons = trade.get("reasons", [])
        if isinstance(reasons, list):
            reasons = json.dumps(reasons)

        trade_id = trade.get("id") or str(uuid.uuid4())
        pnl_usd  = self.calc_pnl_usd(trade, bankroll)

        await self._db.execute("""
            INSERT OR REPLACE INTO trades
            (id, pair, direction, entry, stop_loss, tp1, tp2, tp3,
             risk_pct, rr_ratio, confidence, score, reasons,
             status, exit_price, pnl_pct, pnl_usd,
             tp1_hit, tp2_hit, tp3_hit, sl_hit,
             opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            pnl_usd,
            int(bool(trade.get("tp1_hit", False))),
            int(bool(trade.get("tp2_hit", False))),
            int(bool(trade.get("tp3_hit", False))),
            int(bool(trade.get("sl_hit",  False))),
            trade.get("opened_at", datetime.now(timezone.utc).isoformat()),
            trade.get("closed_at"),
        ))
        await self._db.commit()
        return trade_id

    async def get_open_trades(self) -> list:
        """Get all trades that are still open (not closed yet)."""
        cursor = await self._db.execute(
            "SELECT * FROM trades WHERE closed_at IS NULL ORDER BY opened_at ASC"
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_recent_trades(self, limit: int = 10) -> list:
        """Get most recent closed trades."""
        cursor = await self._db.execute(
            "SELECT * FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT ?",
            (limit,),
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_all_trades(self, limit: int = 50) -> list:
        """Get all trades ordered by opened_at."""
        cursor = await self._db.execute(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        )
        columns = [desc[0] for desc in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

    async def get_stats_multi_period(self, bankroll: float = 1000.0) -> dict:
        """Return stats for weekly (7d), monthly (30d), and annual (365d) periods."""
        result = {}
        for label, days in [("weekly", 7), ("monthly", 30), ("annual", 365)]:
            result[label] = await self.get_stats(days=days, bankroll=bankroll)
        return result

    async def get_stats(self, days: int = 30, bankroll: float = 1000.0) -> dict:
        """Calculate performance statistics for the given period."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        cursor = await self._db.execute(
            "SELECT pnl_pct, pnl_usd, status FROM trades WHERE opened_at >= ? AND closed_at IS NOT NULL",
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
                "total_pnl_usd": 0.0,
                "current_bankroll": bankroll,
                "max_drawdown": 0.0,
                "max_drawdown_usd": 0.0,
                "profit_factor": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "avg_win_usd": 0.0,
                "avg_loss_usd": 0.0,
            }

        pnl_list     = [r[0] for r in rows]
        pnl_usd_list = [r[1] for r in rows]
        wins   = sum(1 for p in pnl_usd_list if p > 0)
        losses = sum(1 for p in pnl_usd_list if p <= 0)
        total  = len(pnl_list)

        win_usd  = [p for p in pnl_usd_list if p > 0]
        loss_usd = [p for p in pnl_usd_list if p < 0]

        gross_profit = sum(win_usd)  if win_usd  else 0.0
        gross_loss   = abs(sum(loss_usd)) if loss_usd else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        # Max drawdown in USD
        running_usd = 0.0
        peak_usd    = 0.0
        max_dd_usd  = 0.0
        for p in pnl_usd_list:
            running_usd += p
            peak_usd = max(peak_usd, running_usd)
            max_dd_usd = max(max_dd_usd, peak_usd - running_usd)

        total_pnl_usd    = round(sum(pnl_usd_list), 2)
        current_bankroll = round(bankroll + total_pnl_usd, 2)

        return {
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round((wins / total) * 100, 1) if total > 0 else 0.0,
            "total_pnl": round(sum(pnl_list), 2),
            "total_pnl_usd": total_pnl_usd,
            "current_bankroll": current_bankroll,
            "max_drawdown": round(max_dd_usd / bankroll * 100, 1) if bankroll else 0.0,
            "max_drawdown_usd": round(max_dd_usd, 2),
            "profit_factor": round(profit_factor, 2),
            "avg_win": round(sum(win_usd) / len(win_usd), 2) if win_usd else 0.0,
            "avg_loss": round(sum(loss_usd) / len(loss_usd), 2) if loss_usd else 0.0,
            "avg_win_usd": round(sum(win_usd) / len(win_usd), 2) if win_usd else 0.0,
            "avg_loss_usd": round(sum(loss_usd) / len(loss_usd), 2) if loss_usd else 0.0,
        }

    async def get_bankroll_history(self, bankroll: float = 1000.0, limit: int = 50) -> list:
        """Retorna histórico de banca: [(data, bankroll_usd), ...] para equity curve."""
        cursor = await self._db.execute(
            "SELECT pnl_usd, closed_at FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at ASC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        history = []
        running = bankroll
        for pnl_usd, closed_at in rows:
            running += (pnl_usd or 0.0)
            history.append({"date": closed_at, "bankroll": round(running, 2), "pnl_usd": pnl_usd or 0.0})
        return history

    async def close(self):
        """Close the database connection."""
        if self._db:
            await self._db.close()
            self._db = None
