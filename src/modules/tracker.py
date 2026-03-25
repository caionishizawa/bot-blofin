"""
Trade Tracker — monitors active trades and detects SL/TP level hits.

tp_count controls the TP structure:
  1 — scalp: close 100% at TP1
  2 — sniper/intraday: 40% at TP1, 60% at TP2 (final)
  3 — swing: 35% at TP1, 45% at TP2, 20% at TP3 (final)
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


# Exit splits per tp_count: (tp1_split, tp2_split, tp3_split)
_TP_SPLITS = {
    1: (1.00, 0.00, 0.00),
    2: (0.40, 0.60, 0.00),
    3: (0.35, 0.45, 0.20),
}

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
        self.tp2       = float(signal.get("tp2") or 0)
        self.tp3       = float(signal.get("tp3") or 0)
        self.tp_count  = int(signal.get("tp_count", 3))
        self.risk_pct  = float(signal.get("risk_pct", 2.0))
        self.rr_ratio  = float(signal.get("rr_ratio", 0.0))
        self.confidence = int(signal.get("confidence", 0))
        self.score     = float(signal.get("score", 0.0))
        self.reasons   = signal.get("reasons", [])
        self.timeframe = signal.get("timeframe", "1H")
        self.trade_style = signal.get("trade_style", "swing")

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
    def final_tp(self) -> str:
        """Event string that signals the final close for this trade's tp_count."""
        return {1: "TP1_HIT", 2: "TP2_HIT", 3: "TP3_HIT"}.get(self.tp_count, "TP3_HIT")

    @property
    def pnl_pct(self) -> float:
        """Current unrealized PNL % based on current_price."""
        ref = self.exit_price if self.exit_price is not None else self.current_price
        if self.direction == "LONG":
            return ((ref - self.entry) / self.entry) * 100
        else:
            return ((self.entry - ref) / self.entry) * 100

    def unrealized_pnl_usd(self, bankroll: float) -> float:
        """PNL não realizado da posição ainda aberta, em USD.

        Usa splits do tp_count: {1: 100%, 2: 40/60, 3: 35/45/20}.
        """
        sl_dist = abs(self.entry - self.stop_loss)
        if sl_dist == 0 or self.entry == 0:
            return 0.0

        risk_amount = bankroll * self.risk_pct / 100

        s1, s2, s3 = _TP_SPLITS.get(self.tp_count, _TP_SPLITS[3])
        remaining = 1.0 - (s1 if self.tp1_hit else 0.0) - (s2 if self.tp2_hit else 0.0) - (s3 if self.tp3_hit else 0.0)
        if remaining <= 0 or self.sl_hit or (self.tp_count == 1 and self.tp1_hit) or (self.tp_count == 2 and self.tp2_hit) or self.tp3_hit:
            return 0.0

        if self.direction == "LONG":
            price_move = self.current_price - self.entry
        else:
            price_move = self.entry - self.current_price

        rr_current = price_move / sl_dist
        return round(risk_amount * rr_current * remaining, 2)

    def _close(self, exit_price: float):
        """Record closing price and timestamp."""
        self.exit_price = exit_price
        self.closed_at = datetime.now(timezone.utc).isoformat()

    def check_levels(self, price: float) -> str | None:
        """Check if price has hit any SL/TP level.

        Returns event string or None. On final TP hit, records exit_price and closed_at.
        tp_count controls which TPs are active:
          1 → only TP1 checked (close 100%)
          2 → TP1 (partial 40%) + TP2 (final close 60%)
          3 → TP1 (35%) + TP2 (45%) + TP3 (final close 20%)
        """
        self.current_price = price
        tc = self.tp_count

        if self.direction == "LONG":
            if not self.sl_hit and price <= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                self._close(self.stop_loss)
                return "SL_HIT"
            # TP3 — only for 3-TP trades
            if tc == 3 and not self.tp3_hit and self.tp3 > 0 and price >= self.tp3:
                self.tp1_hit = True
                self.tp2_hit = True
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                self._close(self.tp3)
                return "TP3_HIT"
            # TP2 — for 2-TP (final) and 3-TP (partial)
            if tc >= 2 and not self.tp2_hit and self.tp2 > 0 and price >= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                if tc == 2:
                    self.tp1_hit = True  # mark partial also done on gap
                    self._close(self.tp2)
                return "TP2_HIT"
            # TP1
            if not self.tp1_hit and self.tp1 > 0 and price >= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                if tc == 1:
                    self.tp2_hit = True
                    self.tp3_hit = True
                    self._close(self.tp1)
                return "TP1_HIT"
        else:  # SHORT
            if not self.sl_hit and price >= self.stop_loss:
                self.sl_hit = True
                self.status = TradeStatus.SL_HIT
                self._close(self.stop_loss)
                return "SL_HIT"
            if tc == 3 and not self.tp3_hit and self.tp3 > 0 and price <= self.tp3:
                self.tp1_hit = True
                self.tp2_hit = True
                self.tp3_hit = True
                self.status = TradeStatus.TP3_HIT
                self._close(self.tp3)
                return "TP3_HIT"
            if tc >= 2 and not self.tp2_hit and self.tp2 > 0 and price <= self.tp2:
                self.tp2_hit = True
                self.status = TradeStatus.TP2_HIT
                if tc == 2:
                    self.tp1_hit = True
                    self._close(self.tp2)
                return "TP2_HIT"
            if not self.tp1_hit and self.tp1 > 0 and price <= self.tp1:
                self.tp1_hit = True
                self.status = TradeStatus.TP1_HIT
                if tc == 1:
                    self.tp2_hit = True
                    self.tp3_hit = True
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
            "tp2":           self.tp2 or None,
            "tp3":           self.tp3 or None,
            "tp_count":      self.tp_count,
            "risk_pct":      self.risk_pct,
            "rr_ratio":      self.rr_ratio,
            "confidence":    self.confidence,
            "score":         self.score,
            "reasons":       self.reasons,
            "timeframe":     self.timeframe,
            "trade_style":   self.trade_style,
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
