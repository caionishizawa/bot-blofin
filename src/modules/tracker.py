"""
Trade Tracker — monitors active trades and detects SL/TP level hits.
"""

from enum import Enum
from datetime import datetime, timezone


class TradeStatus(Enum):
    OPEN = "open"
    TP1_HIT = "tp1_hit"
    TP2_HIT = "tp2_hit"
    TP3_HIT = "tp3_hit"
    SL_HIT = "sl_hit"


class ActiveTrade:
    """Tracks a single active trade with level detection."""

    def __init__(self, signal: dict):
        self.pair = signal["pair"]
        self.direction = signal["direction"]
        self.entry = float(signal["entry"])
        self.stop_loss = float(signal["stop_loss"])
        self.tp1 = float(signal["tp1"])
        self.tp2 = float(signal["tp2"])
        self.tp3 = float(signal["tp3"])
        self.risk_pct = float(signal.get("risk_pct", 2.0))
        self.status = TradeStatus.OPEN
        self.current_price = self.entry
        self.opened_at = datetime.now(timezone.utc).isoformat()

        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False
        self.sl_hit = False

    @property
    def pnl_pct(self) -> float:
        """Calculate current PNL percentage."""
        if self.direction == "LONG":
            return ((self.current_price - self.entry) / self.entry) * 100
        else:
            return ((self.entry - self.current_price) / self.entry) * 100

    def check_levels(self, price: float) -> str | None:
        """Check if price has hit any SL/TP level.

        Returns event string or None.
        """
        self.current_price = price

        if self.direction == "LONG":
            # SL hit
            if not self.sl_hit and price <= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                return "SL_HIT"
            # TP levels
            if not self.tp1_hit and price >= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                return "TP1_HIT"
            if not self.tp2_hit and price >= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                return "TP2_HIT"
            if not self.tp3_hit and price >= self.tp3:
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                return "TP3_HIT"

        else:  # SHORT
            # SL hit
            if not self.sl_hit and price >= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                return "SL_HIT"
            # TP levels
            if not self.tp1_hit and price <= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                return "TP1_HIT"
            if not self.tp2_hit and price <= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                return "TP2_HIT"
            if not self.tp3_hit and price <= self.tp3:
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                return "TP3_HIT"

        return None

    def to_dict(self) -> dict:
        """Serialize trade to dictionary."""
        return {
            "pair": self.pair,
            "direction": self.direction,
            "entry": self.entry,
            "stop_loss": self.stop_loss,
            "tp1": self.tp1,
            "tp2": self.tp2,
            "tp3": self.tp3,
            "risk_pct": self.risk_pct,
            "status": self.status.value,
            "current_price": self.current_price,
            "pnl_pct": self.pnl_pct,
            "opened_at": self.opened_at,
            "tp1_hit": self.tp1_hit,
            "tp2_hit": self.tp2_hit,
            "tp3_hit": self.tp3_hit,
            "sl_hit": self.sl_hit,
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
