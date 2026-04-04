"""
Performance DB — Trade history and metrics.
Uses PostgreSQL (asyncpg) when DATABASE_URL is set, SQLite otherwise.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


def _use_postgres() -> bool:
    url = os.getenv("DATABASE_URL", "")
    return url.startswith("postgres")


# ---------------------------------------------------------------------------
# PostgreSQL backend
# ---------------------------------------------------------------------------

class _PGBackend:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self._pool = None

    async def initialize(self):
        import asyncpg
        # Garante SSL para Render external URL
        dsn = self._dsn
        if "render.com" in dsn and "sslmode" not in dsn:
            dsn = dsn + "?sslmode=require"
        self._pool = await asyncpg.create_pool(dsn, min_size=1, max_size=5)
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id          TEXT PRIMARY KEY,
                    pair        TEXT NOT NULL,
                    direction   TEXT NOT NULL,
                    entry       DOUBLE PRECISION NOT NULL,
                    stop_loss   DOUBLE PRECISION NOT NULL,
                    tp1         DOUBLE PRECISION,
                    tp2         DOUBLE PRECISION,
                    tp3         DOUBLE PRECISION,
                    risk_pct    DOUBLE PRECISION DEFAULT 2.0,
                    rr_ratio    DOUBLE PRECISION DEFAULT 0.0,
                    confidence  INTEGER DEFAULT 0,
                    score       DOUBLE PRECISION DEFAULT 0.0,
                    reasons     TEXT DEFAULT '[]',
                    status      TEXT NOT NULL,
                    exit_price  DOUBLE PRECISION,
                    pnl_pct     DOUBLE PRECISION DEFAULT 0.0,
                    pnl_usd     DOUBLE PRECISION DEFAULT 0.0,
                    tp1_hit     BOOLEAN DEFAULT FALSE,
                    tp2_hit     BOOLEAN DEFAULT FALSE,
                    tp3_hit     BOOLEAN DEFAULT FALSE,
                    sl_hit      BOOLEAN DEFAULT FALSE,
                    tp_count    INTEGER DEFAULT 3,
                    trade_style TEXT DEFAULT 'swing',
                    opened_at   TEXT NOT NULL,
                    closed_at   TEXT
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS groups (
                    chat_id   TEXT PRIMARY KEY,
                    title     TEXT,
                    enabled   BOOLEAN DEFAULT TRUE,
                    added_at  TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory (
                    telegram_id      TEXT PRIMARY KEY,
                    level            TEXT DEFAULT 'iniciante',
                    ask_count_today  INTEGER DEFAULT 0,
                    ask_date         TEXT DEFAULT '',
                    total_asks       INTEGER DEFAULT 0,
                    summary          TEXT DEFAULT '',
                    last_topics      TEXT DEFAULT '[]',
                    updated_at       TEXT NOT NULL
                )
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    id          TEXT PRIMARY KEY,
                    email       TEXT NOT NULL,
                    name        TEXT DEFAULT '',
                    telegram_id TEXT,
                    plan        TEXT NOT NULL,
                    status      TEXT DEFAULT 'active',
                    platform    TEXT NOT NULL,
                    payment_id  TEXT DEFAULT '',
                    expires_at  TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                )
            """)

    async def execute(self, query: str, *args):
        async with self._pool.acquire() as conn:
            # Convert SQLite-style ? placeholders to $1, $2, ...
            pg_query = _to_pg(query)
            await conn.execute(pg_query, *args)

    async def fetchall(self, query: str, *args) -> list:
        async with self._pool.acquire() as conn:
            pg_query = _to_pg(query)
            rows = await conn.fetch(pg_query, *args)
            return [dict(r) for r in rows]

    async def close(self):
        if self._pool:
            await self._pool.close()


def _to_pg(query: str) -> str:
    """Convert SQLite ? placeholders to PostgreSQL $1, $2, ..."""
    i = 0
    result = []
    for ch in query:
        if ch == "?":
            i += 1
            result.append(f"${i}")
        else:
            result.append(ch)
    # SQLite upsert → PostgreSQL upsert
    q = "".join(result)
    q = q.replace("INSERT OR REPLACE INTO", "INSERT INTO")
    q = q.replace(
        "ON CONFLICT(chat_id) DO UPDATE SET enabled=1, title=excluded.title",
        "ON CONFLICT(chat_id) DO UPDATE SET enabled=TRUE, title=EXCLUDED.title",
    )
    return q


# ---------------------------------------------------------------------------
# SQLite backend
# ---------------------------------------------------------------------------

class _SQLiteBackend:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._db = None

    async def initialize(self):
        import aiosqlite
        os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
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
                tp_count    INTEGER DEFAULT 3,
                trade_style TEXT DEFAULT 'swing',
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
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS agent_memory (
                telegram_id      TEXT PRIMARY KEY,
                level            TEXT DEFAULT 'iniciante',
                ask_count_today  INTEGER DEFAULT 0,
                ask_date         TEXT DEFAULT '',
                total_asks       INTEGER DEFAULT 0,
                summary          TEXT DEFAULT '',
                last_topics      TEXT DEFAULT '[]',
                updated_at       TEXT NOT NULL
            )
        """)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                id          TEXT PRIMARY KEY,
                email       TEXT NOT NULL,
                name        TEXT DEFAULT '',
                telegram_id TEXT,
                plan        TEXT NOT NULL,
                status      TEXT DEFAULT 'active',
                platform    TEXT NOT NULL,
                payment_id  TEXT DEFAULT '',
                expires_at  TEXT NOT NULL,
                created_at  TEXT NOT NULL
            )
        """)
        for col, definition in [
            ("rr_ratio",    "REAL DEFAULT 0.0"),
            ("pnl_usd",     "REAL DEFAULT 0.0"),
            ("tp1_hit",     "INTEGER DEFAULT 0"),
            ("tp2_hit",     "INTEGER DEFAULT 0"),
            ("tp3_hit",     "INTEGER DEFAULT 0"),
            ("sl_hit",      "INTEGER DEFAULT 0"),
            ("tp_count",    "INTEGER DEFAULT 3"),
            ("trade_style", "TEXT DEFAULT 'swing'"),
        ]:
            try:
                await self._db.execute(f"ALTER TABLE trades ADD COLUMN {col} {definition}")
            except Exception:
                pass
        await self._db.commit()

    async def execute(self, query: str, *args):
        await self._db.execute(query, args[0] if args and isinstance(args[0], (list, tuple)) else args)
        await self._db.commit()

    async def fetchall(self, query: str, *args) -> list:
        params = args[0] if args and isinstance(args[0], (list, tuple)) else args
        cursor = await self._db.execute(query, params)
        columns = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        return [dict(zip(columns, r)) for r in rows]

    async def close(self):
        if self._db:
            await self._db.close()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class PerformanceDB:
    """Trade history and performance metrics. Auto-selects PostgreSQL or SQLite."""

    def __init__(self, db_path: str = "data/trades.db"):
        self._db_path = db_path
        dsn = os.getenv("DATABASE_URL", "")
        if dsn.startswith("postgres"):
            self._backend = _PGBackend(dsn)
        else:
            self._backend = _SQLiteBackend(db_path)

    async def initialize(self):
        import logging
        try:
            await self._backend.initialize()
        except Exception as e:
            logging.getLogger(__name__).warning(
                "PostgreSQL falhou (%s) — usando SQLite como fallback", e
            )
            self._backend = _SQLiteBackend(self._db_path)
            await self._backend.initialize()

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    async def enable_group(self, chat_id: str, title: str = ""):
        await self._backend.execute("""
            INSERT INTO groups (chat_id, title, enabled, added_at)
            VALUES (?, ?, 1, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled=1, title=excluded.title
        """, (str(chat_id), title, datetime.now(timezone.utc).isoformat()))

    async def disable_group(self, chat_id: str):
        await self._backend.execute(
            "UPDATE groups SET enabled=0 WHERE chat_id=?", (str(chat_id),)
        )

    async def get_enabled_groups(self) -> list:
        rows = await self._backend.fetchall(
            "SELECT chat_id, title FROM groups WHERE enabled=1"
        )
        return rows

    async def list_groups(self) -> list:
        return await self._backend.fetchall(
            "SELECT chat_id, title, enabled FROM groups ORDER BY added_at DESC"
        )

    # ------------------------------------------------------------------
    # PNL calculation
    # ------------------------------------------------------------------

    # Exit splits per tp_count (must mirror tracker._TP_SPLITS)
    _TP_SPLITS = {1: (1.00, 0.00, 0.00), 2: (0.40, 0.60, 0.00), 3: (0.35, 0.45, 0.20)}

    @staticmethod
    def calc_pnl_usd(trade: dict, bankroll: float) -> float:
        risk_pct    = trade.get("risk_pct", 2.0)
        risk_amount = bankroll * risk_pct / 100
        entry       = trade.get("entry", 0)
        stop_loss   = trade.get("stop_loss", 0)
        tp1         = trade.get("tp1") or 0
        tp2         = trade.get("tp2") or 0
        tp3         = trade.get("tp3") or 0
        tp_count    = int(trade.get("tp_count", 3))

        if not entry or not stop_loss:
            return 0.0
        sl_dist = abs(entry - stop_loss)
        if sl_dist == 0:
            return 0.0

        tp1_hit = bool(trade.get("tp1_hit", False))
        tp2_hit = bool(trade.get("tp2_hit", False))
        tp3_hit = bool(trade.get("tp3_hit", False))
        sl_hit  = bool(trade.get("sl_hit",  False))

        s1, s2, s3 = PerformanceDB._TP_SPLITS.get(tp_count, (0.35, 0.45, 0.20))

        pnl = 0.0
        if tp1_hit and tp1:
            pnl += risk_amount * (abs(tp1 - entry) / sl_dist) * s1
        if tp2_hit and tp2:
            pnl += risk_amount * (abs(tp2 - entry) / sl_dist) * s2
        if tp3_hit and tp3:
            pnl += risk_amount * (abs(tp3 - entry) / sl_dist) * s3
        if sl_hit:
            remaining = 1.0 - (s1 if tp1_hit else 0) - (s2 if tp2_hit else 0)
            pnl -= risk_amount * remaining

        return round(pnl, 2)

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    async def save_trade(self, trade: dict, bankroll: float = 1000.0) -> str:
        reasons = trade.get("reasons", [])
        if isinstance(reasons, list):
            reasons = json.dumps(reasons)

        trade_id = trade.get("id") or str(uuid.uuid4())
        pnl_usd  = self.calc_pnl_usd(trade, bankroll)

        await self._backend.execute("""
            INSERT OR REPLACE INTO trades
            (id, pair, direction, entry, stop_loss, tp1, tp2, tp3,
             risk_pct, rr_ratio, confidence, score, reasons,
             status, exit_price, pnl_pct, pnl_usd,
             tp1_hit, tp2_hit, tp3_hit, sl_hit,
             tp_count, trade_style,
             opened_at, closed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            bool(trade.get("tp1_hit", False)),
            bool(trade.get("tp2_hit", False)),
            bool(trade.get("tp3_hit", False)),
            bool(trade.get("sl_hit",  False)),
            int(trade.get("tp_count", 3)),
            trade.get("trade_style", "swing"),
            trade.get("opened_at", datetime.now(timezone.utc).isoformat()),
            trade.get("closed_at"),
        ))
        return trade_id

    async def get_open_trades(self) -> list:
        return await self._backend.fetchall(
            "SELECT * FROM trades WHERE closed_at IS NULL ORDER BY opened_at ASC"
        )

    async def get_recent_trades(self, limit: int = 10) -> list:
        return await self._backend.fetchall(
            "SELECT * FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT ?",
            (limit,),
        )

    async def get_all_trades(self, limit: int = 50) -> list:
        return await self._backend.fetchall(
            "SELECT * FROM trades ORDER BY opened_at DESC LIMIT ?", (limit,)
        )

    async def get_stats_multi_period(self, bankroll: float = 1000.0) -> dict:
        result = {}
        for label, days in [("weekly", 7), ("monthly", 30), ("annual", 365)]:
            result[label] = await self.get_stats(days=days, bankroll=bankroll)
        return result

    async def get_stats(self, days: int = 30, bankroll: float = 1000.0) -> dict:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await self._backend.fetchall(
            "SELECT pnl_pct, pnl_usd, status FROM trades WHERE opened_at >= ? AND closed_at IS NOT NULL",
            (since,),
        )

        if not rows:
            return {
                "total_trades": 0, "wins": 0, "losses": 0,
                "win_rate": 0.0, "total_pnl": 0.0, "total_pnl_usd": 0.0,
                "current_bankroll": bankroll, "max_drawdown": 0.0,
                "max_drawdown_usd": 0.0, "profit_factor": 0.0,
                "avg_win": 0.0, "avg_loss": 0.0,
                "avg_win_usd": 0.0, "avg_loss_usd": 0.0,
            }

        pnl_list     = [r["pnl_pct"] for r in rows]
        pnl_usd_list = [r["pnl_usd"] for r in rows]
        wins   = sum(1 for p in pnl_usd_list if p > 0)
        losses = sum(1 for p in pnl_usd_list if p < 0)
        total  = len(pnl_list)

        win_usd  = [p for p in pnl_usd_list if p > 0]
        loss_usd = [p for p in pnl_usd_list if p < 0]

        gross_profit  = sum(win_usd)  if win_usd  else 0.0
        gross_loss    = abs(sum(loss_usd)) if loss_usd else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf")

        running_usd = peak_usd = max_dd_usd = 0.0
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

    async def get_sizing_stats(self, bankroll: float = 1000.0) -> dict:
        """Retorna métricas para o position sizer dinâmico:
        current_streak, drawdown_pct (últimos 30d), win_rate (últimos 20 trades).
        """
        # Últimos 20 trades fechados (para streak e win rate recente)
        rows = await self._backend.fetchall(
            "SELECT pnl_usd FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at DESC LIMIT 20",
            (),
        )
        if not rows:
            return {"current_streak": 0, "drawdown_pct": 0.0, "win_rate_recent": 50.0, "total_closed": 0}

        pnl_list = [r["pnl_usd"] or 0.0 for r in rows]

        # Streak: conta vitórias/derrotas consecutivas a partir do mais recente
        streak = 0
        first = pnl_list[0]
        if first > 0:
            for p in pnl_list:
                if p > 0:
                    streak += 1
                else:
                    break
        elif first < 0:
            for p in pnl_list:
                if p < 0:
                    streak -= 1
                else:
                    break

        # Win rate recente (últimos 20)
        wins = sum(1 for p in pnl_list if p > 0)
        win_rate = round(wins / len(pnl_list) * 100, 1)

        # Drawdown atual (30 dias)
        stats_30 = await self.get_stats(days=30, bankroll=bankroll)
        drawdown_pct = stats_30.get("max_drawdown", 0.0)

        return {
            "current_streak":   streak,       # positivo = wins seguidos, negativo = losses
            "drawdown_pct":     drawdown_pct,  # % de drawdown dos últimos 30d
            "win_rate_recent":  win_rate,      # win rate últimos 20 trades
            "total_closed":     len(pnl_list),
        }

    async def get_stats_by_style(self, days: int = 30, bankroll: float = 1000.0) -> dict:
        """Performance breakdown por estilo: scalp / daytrade / swing."""
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = await self._backend.fetchall(
            """SELECT pnl_usd, trade_style
               FROM trades
               WHERE opened_at >= ? AND closed_at IS NOT NULL""",
            (since,),
        )
        styles = {"scalp": [], "daytrade": [], "swing": []}
        for r in rows:
            style = r.get("trade_style") or "swing"
            if style not in styles:
                style = "swing"
            styles[style].append(r["pnl_usd"] or 0.0)

        result = {}
        for style, pnl_list in styles.items():
            if not pnl_list:
                result[style] = {"trades": 0, "win_rate": 0.0, "total_pnl_usd": 0.0, "avg_pnl_usd": 0.0}
                continue
            wins = sum(1 for p in pnl_list if p > 0)
            result[style] = {
                "trades":        len(pnl_list),
                "win_rate":      round(wins / len(pnl_list) * 100, 1),
                "total_pnl_usd": round(sum(pnl_list), 2),
                "avg_pnl_usd":   round(sum(pnl_list) / len(pnl_list), 2),
            }
        return result

    async def get_bankroll_history(self, bankroll: float = 1000.0, limit: int = 50) -> list:
        rows = await self._backend.fetchall(
            "SELECT pnl_usd, closed_at FROM trades WHERE closed_at IS NOT NULL ORDER BY closed_at ASC LIMIT ?",
            (limit,),
        )
        history = []
        running = bankroll
        for r in rows:
            running += (r["pnl_usd"] or 0.0)
            history.append({"date": r["closed_at"], "bankroll": round(running, 2), "pnl_usd": r["pnl_usd"] or 0.0})
        return history

    async def reset_trades(self):
        """Apaga todos os trades do histórico (zera o placar)."""
        await self._backend.execute("DELETE FROM trades")

    async def close(self):
        await self._backend.close()

    # ------------------------------------------------------------------
    # Subscribers (VIP checkout)
    # ------------------------------------------------------------------

    async def add_subscriber(
        self,
        email: str,
        name: str = "",
        telegram_id: str = None,
        plan: str = "monthly",
        expires_at: str = "",
        platform: str = "manual",
        payment_id: str = "",
    ) -> str:
        """
        Adiciona ou renova assinante VIP.
        Se já existir registro com mesmo email/payment_id, atualiza o status e expiry.
        Retorna o ID gerado.
        """
        import uuid
        sub_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        # Tenta atualizar registro existente pelo email
        existing = await self._backend.fetchall(
            "SELECT id FROM subscribers WHERE email=? ORDER BY created_at DESC LIMIT 1",
            (email,),
        )
        if existing:
            sub_id = existing[0]["id"]
            await self._backend.execute(
                """UPDATE subscribers
                   SET telegram_id=?, plan=?, status='active', platform=?,
                       payment_id=?, expires_at=?
                   WHERE id=?""",
                (telegram_id, plan, platform, payment_id, expires_at, sub_id),
            )
        else:
            await self._backend.execute(
                """INSERT INTO subscribers
                       (id, email, name, telegram_id, plan, status, platform, payment_id, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                (sub_id, email, name, telegram_id, plan, platform, payment_id, expires_at, now),
            )
        return sub_id

    async def is_vip_subscriber(self, telegram_id: str) -> bool:
        """Retorna True se o telegram_id tem assinatura ativa e não expirada."""
        if not telegram_id:
            return False
        now = datetime.now(timezone.utc).isoformat()
        rows = await self._backend.fetchall(
            """SELECT id FROM subscribers
               WHERE telegram_id=? AND status='active' AND expires_at > ?
               LIMIT 1""",
            (str(telegram_id), now),
        )
        return len(rows) > 0

    async def get_subscriber(self, telegram_id: str) -> dict:
        """Retorna dados da assinatura ativa do telegram_id, ou {} se não encontrado."""
        if not telegram_id:
            return {}
        now = datetime.now(timezone.utc).isoformat()
        rows = await self._backend.fetchall(
            """SELECT * FROM subscribers
               WHERE telegram_id=? AND status='active'
               ORDER BY expires_at DESC LIMIT 1""",
            (str(telegram_id),),
        )
        return rows[0] if rows else {}

    async def list_subscribers(self, active_only: bool = True) -> list:
        """Lista todos os assinantes (por padrão apenas ativos e não expirados)."""
        now = datetime.now(timezone.utc).isoformat()
        if active_only:
            rows = await self._backend.fetchall(
                "SELECT * FROM subscribers WHERE status='active' AND expires_at > ? ORDER BY created_at DESC",
                (now,),
            )
        else:
            rows = await self._backend.fetchall(
                "SELECT * FROM subscribers ORDER BY created_at DESC",
                (),
            )
        return rows

    async def revoke_subscriber(self, email: str = "", payment_id: str = "") -> None:
        """Revoga acesso VIP por email ou payment_id (reembolso/chargeback)."""
        if payment_id:
            await self._backend.execute(
                "UPDATE subscribers SET status='refunded' WHERE payment_id=?",
                (payment_id,),
            )
        elif email:
            await self._backend.execute(
                "UPDATE subscribers SET status='refunded' WHERE email=?",
                (email,),
            )

    async def expire_stale_subscribers(self) -> int:
        """
        Marca como expiradas as assinaturas vencidas.
        Chamar periodicamente (ex: a cada 6h pelo scheduler do bot).
        Retorna quantidade de registros atualizados.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows_before = await self._backend.fetchall(
            "SELECT COUNT(*) as n FROM subscribers WHERE status='active' AND expires_at <= ?",
            (now,),
        )
        count = rows_before[0]["n"] if rows_before else 0
        await self._backend.execute(
            "UPDATE subscribers SET status='expired' WHERE status='active' AND expires_at <= ?",
            (now,),
        )
        return count
