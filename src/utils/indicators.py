"""
Technical Indicators + Signal Detection.

Converts BloFin candle data to DataFrame, calculates 12+ indicators,
and detects trading signals via confluence logic.

All indicators are calculated with pandas/numpy (no external TA library needed).
"""

import pandas as pd
import numpy as np


def candles_to_df(candles: list) -> pd.DataFrame:
    """Convert BloFin candle list to a pandas DataFrame.

    BloFin candle format: [timestamp, open, high, low, close, vol, ...]
    """
    rows = []
    for c in candles:
        rows.append({
            "timestamp": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "volume": float(c[5]) if len(c) > 5 else 0.0,
        })
    df = pd.DataFrame(rows)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


# ─── Indicator calculations ────────────────────────────────

def _ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2.0):
    mid = series.rolling(window).mean()
    std = series.rolling(window).std()
    upper = mid + (std * num_std)
    lower = mid - (std * num_std)
    return upper, mid, lower


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, min_periods=window).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14):
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    plus_dm = (high - prev_high).clip(lower=0)
    minus_dm = (prev_low - low).clip(lower=0)

    # Zero out when the other is larger
    plus_dm = plus_dm.where(plus_dm > minus_dm, 0.0)
    minus_dm = minus_dm.where(minus_dm > plus_dm, 0.0)

    atr_val = _atr(high, low, close, window)

    plus_di = 100 * _ema(plus_dm, window) / atr_val
    minus_di = 100 * _ema(minus_dm, window) / atr_val

    dx = (plus_di - minus_di).abs() / (plus_di + minus_di) * 100
    adx_val = _ema(dx, window)

    return adx_val, plus_di, minus_di


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add all technical indicators to the DataFrame."""
    close = df["close"]
    high = df["high"]
    low = df["low"]

    # EMAs
    df["ema9"] = _ema(close, 9)
    df["ema21"] = _ema(close, 21)

    # RSI
    df["rsi"] = _rsi(close, 14)

    # MACD
    macd_line, macd_signal, macd_hist = _macd(close)
    df["macd"] = macd_line
    df["macd_signal"] = macd_signal
    df["macd_hist"] = macd_hist

    # Bollinger Bands
    bb_upper, bb_mid, bb_lower = _bollinger_bands(close)
    df["bb_upper"] = bb_upper
    df["bb_mid"] = bb_mid
    df["bb_lower"] = bb_lower
    df["bb_width"] = (bb_upper - bb_lower) / bb_mid

    # ATR
    df["atr"] = _atr(high, low, close, 14)

    # ADX
    adx_val, adx_pos, adx_neg = _adx(high, low, close, 14)
    df["adx"] = adx_val
    df["adx_pos"] = adx_pos
    df["adx_neg"] = adx_neg

    return df


def detect_signal(df: pd.DataFrame, scalp: bool = False, bar: str = "1H") -> dict | None:
    """Detect trading signal based on confluence of indicators.

    Requires minimum 3 confluences to generate a signal.
    scalp=True uses tighter ATR multipliers suited for 15m entries.
    Returns signal dict or None.
    """
    if len(df) < 50:
        return None

    last = df.iloc[-1]
    prev = df.iloc[-2]

    # Skip if key indicators are NaN
    required = ["ema9", "ema21", "rsi", "macd", "macd_signal", "adx", "atr", "bb_upper", "bb_lower"]
    for col in required:
        if col not in df.columns or pd.isna(last.get(col)):
            return None

    long_reasons = []
    short_reasons = []

    # 1. EMA Cross
    if last["ema9"] > last["ema21"] and prev["ema9"] <= prev["ema21"]:
        long_reasons.append("EMA9 crossed above EMA21")
    elif last["ema9"] < last["ema21"] and prev["ema9"] >= prev["ema21"]:
        short_reasons.append("EMA9 crossed below EMA21")

    # EMA trend alignment
    if last["ema9"] > last["ema21"]:
        long_reasons.append("EMA9 > EMA21 (bullish trend)")
    elif last["ema9"] < last["ema21"]:
        short_reasons.append("EMA9 < EMA21 (bearish trend)")

    # 2. RSI
    if last["rsi"] < 35:
        long_reasons.append(f"RSI oversold ({last['rsi']:.1f})")
    elif last["rsi"] > 65:
        short_reasons.append(f"RSI overbought ({last['rsi']:.1f})")

    # 3. MACD
    if last["macd"] > last["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
        long_reasons.append("MACD bullish crossover")
    elif last["macd"] < last["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
        short_reasons.append("MACD bearish crossover")

    if last["macd_hist"] > 0:
        long_reasons.append("MACD histogram positive")
    elif last["macd_hist"] < 0:
        short_reasons.append("MACD histogram negative")

    # 4. Bollinger Bands
    if last["close"] <= last["bb_lower"]:
        long_reasons.append("Price at lower Bollinger Band")
    elif last["close"] >= last["bb_upper"]:
        short_reasons.append("Price at upper Bollinger Band")

    # 5. ADX — strong trend
    if last["adx"] > 25:
        if last["adx_pos"] > last["adx_neg"]:
            long_reasons.append(f"Strong bullish trend (ADX={last['adx']:.1f})")
        else:
            short_reasons.append(f"Strong bearish trend (ADX={last['adx']:.1f})")

    # 6. Volume confirmation
    vol_avg = df["volume"].rolling(20).mean().iloc[-1]
    if not pd.isna(vol_avg) and vol_avg > 0 and last["volume"] > vol_avg * 1.2:
        if len(long_reasons) >= len(short_reasons):
            long_reasons.append("Volume above average")
        else:
            short_reasons.append("Volume above average")

    # Determine direction
    min_confluence = 3

    if len(long_reasons) >= min_confluence and len(long_reasons) > len(short_reasons):
        direction = "LONG"
        reasons = long_reasons
    elif len(short_reasons) >= min_confluence and len(short_reasons) > len(long_reasons):
        direction = "SHORT"
        reasons = short_reasons
    else:
        return None

    # Calculate entry, SL, TP levels
    entry = float(last["close"])
    atr = float(last["atr"])

    # TP/SL multipliers por tier de timeframe
    # TP1 = parcial de proteção (breakeven trigger)
    # TP2 = alvo principal de lucro
    # TP3 = runner (deixa rodar)
    bar_upper = bar.upper() if bar else "1H"
    if scalp:
        # 15m/30m — scalp rápido: stop curto, alvos definidos
        sl_mult, tp1_mult, tp2_mult, tp3_mult = 1.0, 0.8, 1.5, 2.5
    elif bar_upper in ("4H", "1D", "3D", "1W"):
        # 4H/1D — swing/longo prazo: stop espaçado, alvos estendidos
        # SL: 2 ATR | TP1: 1 ATR (20%) | TP2: 4 ATR (50%) | TP3: 8 ATR (30%)
        sl_mult, tp1_mult, tp2_mult, tp3_mult = 2.0, 1.0, 4.0, 8.0
    else:
        # 1H/2H — intraday: intermediário
        sl_mult, tp1_mult, tp2_mult, tp3_mult = 1.5, 1.2, 2.5, 4.5

    if direction == "LONG":
        stop_loss = entry - (atr * sl_mult)
        tp1 = entry + (atr * tp1_mult)
        tp2 = entry + (atr * tp2_mult)
        tp3 = entry + (atr * tp3_mult)
    else:
        stop_loss = entry + (atr * sl_mult)
        tp1 = entry - (atr * tp1_mult)
        tp2 = entry - (atr * tp2_mult)
        tp3 = entry - (atr * tp3_mult)

    risk = abs(entry - stop_loss)
    reward = abs(tp2 - entry)
    rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

    # Score 0-10: signals start at 7.1 (3 confluences) and go up to 10.0 (7 confluences).
    # Formula: 5.0 base + (reasons / 7) * 5.0 — keeps distribution in the 7-10 range
    # since the scanner already requires min 3 confluences to emit a signal.
    MAX_REASONS = 7.0
    score_10 = round(5.0 + (len(reasons) / MAX_REASONS) * 5.0, 1)
    score_10 = min(10.0, score_10)
    confidence = min(100, int(score_10 * 10))

    return {
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "score": score_10,
        "confidence": confidence,
        "rr_ratio": rr_ratio,
        "risk_pct": 2.0,   # % da banca arriscada por trade (fixo — sobrescrito pelo config)
        "reasons": reasons,
    }
