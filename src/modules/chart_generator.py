"""
Chart Generator — TradingView-style dark charts with signal visualization.
"""

import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle


# Dark theme colors
COLORS = {
    "bg": "#131722",
    "panel": "#1e222d",
    "text": "#d1d4dc",
    "grid": "#363a45",
    "green": "#26a69a",
    "red": "#ef5350",
    "blue": "#2196f3",
    "orange": "#ff9800",
    "purple": "#ab47bc",
    "entry": "#2196f3",
    "sl": "#ef5350",
    "tp": "#26a69a",
    "volume_up": "#26a69a80",
    "volume_down": "#ef535080",
}


def create_chart(signal: dict, config: dict) -> io.BytesIO:
    """Generate a signal chart PNG and return as BytesIO buffer.

    Args:
        signal: dict with direction, entry, stop_loss, tp1/2/3, candles_df
        config: dict with chart settings (width, height, watermark, etc.)
    """
    chart_cfg = config.get("chart", {})
    width = chart_cfg.get("width", 1200)
    height = chart_cfg.get("height", 800)
    n_candles = chart_cfg.get("candles", 80)
    watermark = chart_cfg.get("watermark", "")

    df = signal.get("candles_df")
    if df is None or df.empty:
        return None

    # Take last N candles
    df = df.tail(n_candles).copy().reset_index(drop=True)

    fig, axes = plt.subplots(
        4, 1,
        figsize=(width / 100, height / 100),
        dpi=100,
        gridspec_kw={"height_ratios": [4, 1, 1, 1]},
        facecolor=COLORS["bg"],
    )

    ax_price, ax_vol, ax_rsi, ax_macd = axes

    for ax in axes:
        ax.set_facecolor(COLORS["panel"])
        ax.tick_params(colors=COLORS["text"], labelsize=8)
        ax.grid(True, color=COLORS["grid"], alpha=0.3, linewidth=0.5)
        for spine in ax.spines.values():
            spine.set_color(COLORS["grid"])

    x = np.arange(len(df))

    # --- Candlestick chart ---
    for i, row in df.iterrows():
        color = COLORS["green"] if row["close"] >= row["open"] else COLORS["red"]
        # Body
        body_bottom = min(row["open"], row["close"])
        body_height = abs(row["close"] - row["open"])
        ax_price.add_patch(Rectangle(
            (i - 0.35, body_bottom), 0.7, body_height if body_height > 0 else 0.01,
            facecolor=color, edgecolor=color, linewidth=0.5
        ))
        # Wicks
        ax_price.plot([i, i], [row["low"], body_bottom], color=color, linewidth=0.8)
        ax_price.plot([i, i], [min(row["open"], row["close"]) + body_height, row["high"]],
                      color=color, linewidth=0.8)

    # EMAs
    if "ema9" in df.columns:
        ax_price.plot(x, df["ema9"], color=COLORS["orange"], linewidth=1, label="EMA9", alpha=0.8)
    if "ema21" in df.columns:
        ax_price.plot(x, df["ema21"], color=COLORS["purple"], linewidth=1, label="EMA21", alpha=0.8)

    # Bollinger Bands
    if "bb_upper" in df.columns:
        ax_price.plot(x, df["bb_upper"], color=COLORS["blue"], linewidth=0.5, alpha=0.4)
        ax_price.plot(x, df["bb_lower"], color=COLORS["blue"], linewidth=0.5, alpha=0.4)
        ax_price.fill_between(x, df["bb_lower"], df["bb_upper"], color=COLORS["blue"], alpha=0.05)

    # Signal levels (horizontal lines + zones)
    entry = signal.get("entry")
    sl = signal.get("stop_loss")
    tp1 = signal.get("tp1")
    tp2 = signal.get("tp2")
    tp3 = signal.get("tp3")

    if entry:
        ax_price.axhline(entry, color=COLORS["entry"], linestyle="--", linewidth=1.2, label=f"Entry {entry:.2f}")
    if sl:
        ax_price.axhline(sl, color=COLORS["sl"], linestyle="--", linewidth=1.2, label=f"SL {sl:.2f}")
        if entry:
            ax_price.fill_between(x, sl, entry, color=COLORS["sl"], alpha=0.08)
    if tp1:
        ax_price.axhline(tp1, color=COLORS["tp"], linestyle=":", linewidth=0.8, alpha=0.7, label=f"TP1 {tp1:.2f}")
    if tp2:
        ax_price.axhline(tp2, color=COLORS["tp"], linestyle=":", linewidth=0.8, alpha=0.8, label=f"TP2 {tp2:.2f}")
    if tp3:
        ax_price.axhline(tp3, color=COLORS["tp"], linestyle=":", linewidth=0.8, alpha=0.9, label=f"TP3 {tp3:.2f}")
        if entry:
            ax_price.fill_between(x, entry, tp3, color=COLORS["tp"], alpha=0.06)

    # Title
    pair = signal.get("pair", "")
    direction = signal.get("direction", "")
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio", 0)
    title = f"{pair}  {direction}  |  Conf: {confidence}%  |  R:R {rr}:1"
    ax_price.set_title(title, color=COLORS["text"], fontsize=11, fontweight="bold", pad=10)
    ax_price.legend(loc="upper left", fontsize=7, facecolor=COLORS["panel"],
                    edgecolor=COLORS["grid"], labelcolor=COLORS["text"])

    # Watermark
    if watermark:
        ax_price.text(0.98, 0.02, watermark, transform=ax_price.transAxes,
                      fontsize=9, color=COLORS["text"], alpha=0.3,
                      ha="right", va="bottom")

    # --- Volume ---
    vol_colors = [COLORS["volume_up"] if df["close"].iloc[i] >= df["open"].iloc[i]
                  else COLORS["volume_down"] for i in range(len(df))]
    ax_vol.bar(x, df["volume"], color=vol_colors, width=0.7)
    ax_vol.set_ylabel("Vol", color=COLORS["text"], fontsize=8)

    # --- RSI ---
    if "rsi" in df.columns:
        ax_rsi.plot(x, df["rsi"], color=COLORS["blue"], linewidth=1)
        ax_rsi.axhline(70, color=COLORS["red"], linewidth=0.5, linestyle="--", alpha=0.5)
        ax_rsi.axhline(30, color=COLORS["green"], linewidth=0.5, linestyle="--", alpha=0.5)
        ax_rsi.fill_between(x, 30, 70, color=COLORS["grid"], alpha=0.1)
        ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI", color=COLORS["text"], fontsize=8)

    # --- MACD ---
    if "macd" in df.columns:
        ax_macd.plot(x, df["macd"], color=COLORS["blue"], linewidth=1, label="MACD")
        ax_macd.plot(x, df["macd_signal"], color=COLORS["orange"], linewidth=1, label="Signal")
        hist = df["macd_hist"]
        hist_colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in hist]
        ax_macd.bar(x, hist, color=hist_colors, width=0.7, alpha=0.5)
    ax_macd.set_ylabel("MACD", color=COLORS["text"], fontsize=8)

    # Clean up x-axis
    for ax in axes[:-1]:
        ax.set_xticklabels([])
    ax_macd.set_xlim(-1, len(df))

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=COLORS["bg"], bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def create_pnl_chart(trades: list, config: dict) -> io.BytesIO:
    """Generate an equity curve chart from trade history.

    Args:
        trades: list of dicts with 'pnl_pct' key
        config: chart config dict
    """
    chart_cfg = config.get("chart", {})
    watermark = chart_cfg.get("watermark", "")

    pnl_values = [t["pnl_pct"] for t in trades]
    cumulative = np.cumsum(pnl_values)

    fig, ax = plt.subplots(figsize=(10, 5), dpi=100, facecolor=COLORS["bg"])
    ax.set_facecolor(COLORS["panel"])
    ax.tick_params(colors=COLORS["text"], labelsize=8)
    ax.grid(True, color=COLORS["grid"], alpha=0.3, linewidth=0.5)
    for spine in ax.spines.values():
        spine.set_color(COLORS["grid"])

    x = np.arange(1, len(cumulative) + 1)

    # Fill green above 0, red below 0
    ax.fill_between(x, cumulative, 0,
                    where=(cumulative >= 0), color=COLORS["green"], alpha=0.2)
    ax.fill_between(x, cumulative, 0,
                    where=(cumulative < 0), color=COLORS["red"], alpha=0.2)
    ax.plot(x, cumulative, color=COLORS["blue"], linewidth=2)
    ax.axhline(0, color=COLORS["text"], linewidth=0.5, alpha=0.3)

    # Markers for each trade
    for i, val in enumerate(cumulative):
        color = COLORS["green"] if pnl_values[i] >= 0 else COLORS["red"]
        ax.scatter(i + 1, val, color=color, s=30, zorder=5)

    total_pnl = cumulative[-1] if len(cumulative) > 0 else 0
    wins = sum(1 for p in pnl_values if p > 0)
    wr = (wins / len(pnl_values) * 100) if pnl_values else 0

    ax.set_title(
        f"Equity Curve  |  {len(trades)} trades  |  PNL: {total_pnl:+.1f}%  |  WR: {wr:.0f}%",
        color=COLORS["text"], fontsize=11, fontweight="bold", pad=10
    )
    ax.set_xlabel("Trade #", color=COLORS["text"], fontsize=9)
    ax.set_ylabel("Cumulative PNL %", color=COLORS["text"], fontsize=9)

    if watermark:
        ax.text(0.98, 0.02, watermark, transform=ax.transAxes,
                fontsize=9, color=COLORS["text"], alpha=0.3, ha="right", va="bottom")

    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=COLORS["bg"], bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
