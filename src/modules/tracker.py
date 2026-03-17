"""
Trade Tracker — monitors active trades and detects SL/TP level hits.
"""

import uuid
from enum import Enum
from datetime import datetime, timezone


class TradeStatus(Enum):
    OPEN    = "open"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    TP3_HIT = "tp3_hit"
    SL_HIT  = "sl_hit"


# PnL mapping: what % of the move is realized at each event
_TP_EXIT_PRICE_KEY = {
    "TP1_HIT": "tp1",
    "TP2_HIT": "tp2",
    "TP3_HIT": "tp3",
    "SL_HIT":  "stop_loss",
}


class ActiveTrade:
    """Tracks a single active trade with level detection."""

    def __init__(self, signal: dict):
        self.id        = signal.get("id") or str(uuid.uuid4())
        self.pair      = signal["pair"]
        self.direction = signal["direction"]
        self.entry     = float(signal["entry"])
        self.stop_loss = float(signal["stop_loss"])
        self.tp1       = float(signal["tp1"])
        self.tp2       = float(signal["tp2"])
        self.tp3       = float(signal["tp3"])
        self.risk_pct  = float(signal.get("risk_pct", 2.0))
        self.rr_ratio  = float(signal.get("rr_ratio", 0.0))
        self.confidence = int(signal.get("confidence", 0))
        self.score     = float(signal.get("score", 0.0))
        self.reasons   = signal.get("reasons", [])
        self.timeframe = signal.get("timeframe", "1H")

        self.status        = TradeStatus.OPEN
        self.current_price = self.entry
        self.exit_price: float | None = None
        self.opened_at     = datetime.now(timezone.utc).isoformat()
        self.closed_at: str | None = None

        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False
        self.sl_hit  = False

    @property
    def pnl_pct(self) -> float:
        """Current unrealized PNL % based on current_price."""
        ref = self.exit_price if self.exit_price is not None else self.current_price
        if self.direction == "LONG":
            return ((ref - self.entry) / self.entry) * 100
        else:
            return ((self.entry - ref) / self.entry) * 100

    def _close(self, exit_price: float):
        """Record closing price and timestamp."""
        self.exit_price = exit_price
        self.closed_at = datetime.now(timezone.utc).isoformat()

    def check_levels(self, price: float) -> str | None:
        """Check if price has hit any SL/TP level.

        Returns event string or None. On hit, records exit_price and closed_at.
        """
        self.current_price = price

        if self.direction == "LONG":
            if not self.sl_hit and price <= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                self._close(self.stop_loss)
                return "SL_HIT"
            if not self.tp3_hit and price >= self.tp3:
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                self._close(self.tp3)
                return "TP3_HIT"
            if not self.tp2_hit and price >= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                self._close(self.tp2)
                return "TP2_HIT"
            if not self.tp1_hit and price >= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                self._close(self.tp1)
                return "TP1_HIT"
        else:  # SHORT
            if not self.sl_hit and price >= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                self._close(self.stop_loss)
                return "SL_HIT"
            if not self.tp3_hit and price <= self.tp3:
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                self._close(self.tp3)
                return "TP3_HIT"
            if not self.tp2_hit and price <= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                self._close(self.tp2)
                return "TP2_HIT"
            if not self.tp1_hit and price <= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                self._close(self.tp1)
                return "TP1_HIT"

        return None

    def to_dict(self) -> dict:
        """Serialize trade to dictionary."""
        return {
            "id":            self.id,
            "pair":          self.pair,
            "direction":     self.direction,
            "entry":         self.entry,
            "stop_loss":     self.stop_loss,
            "tp1":           self.tp1,
            "tp2":           self.tp2,
            "tp3":           self.tp3,
            "risk_pct":      self.risk_pct,
            "rr_ratio":      self.rr_ratio,
            "confidence":    self.confidence,
            "score":         self.score,
            "reasons":       self.reasons,
            "timeframe":     self.timeframe,
            "status":        self.status.value,
            "current_price": self.current_price,
            "exit_price":    self.exit_price,
            "pnl_pct":       round(self.pnl_pct, 3),
            "opened_at":     self.opened_at,
            "closed_at":     self.closed_at,
            "tp1_hit":       self.tp1_hit,
            "tp2_hit":       self.tp2_hit,
            "tp3_hit":       self.tp3_hit,
            "sl_hit":        self.sl_hit,
        }


class TradeTracker:
    """Manages multiple active trades."""

    def __init__(self):
        self.active_trades: dict[str, ActiveTrade] = {}

    def add_trade(self, signal: dict) -> ActiveTrade:
        trade = ActiveTrade(signal)
        self.active_trades[trade.pair] = trade
        return trade

    def update_price(self, pair: str, price: float) -> str | None:
        trade = self.active_trades.get(pair)
        if trade is None:
            return None
        return trade.check_levels(price)

    def remove_trade(self, pair: str):
        self.active_trades.pop(pair, None)

    def get_all(self) -> list[dict]:
        return [t.to_dict() for t in self.active_trades.values()]
