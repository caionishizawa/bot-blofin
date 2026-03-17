"""
Chart Generator — TradingView-style dark charts with signal visualization.
"""

import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle, FancyBboxPatch
from datetime import datetime, timezone


# Dark theme colors — TradingView inspired
COLORS = {
    "bg":           "#0d1117",
    "panel":        "#161b22",
    "panel2":       "#1c2128",
    "text":         "#c9d1d9",
    "text_dim":     "#8b949e",
    "grid":         "#21262d",
    "green":        "#3fb950",
    "green_dim":    "#3fb95030",
    "red":          "#f85149",
    "red_dim":      "#f8514930",
    "blue":         "#58a6ff",
    "blue_dim":     "#58a6ff20",
    "orange":       "#d29922",
    "purple":       "#bc8cff",
    "entry":        "#58a6ff",
    "entry_dim":    "#58a6ff15",
    "sl":           "#f85149",
    "sl_dim":       "#f8514915",
    "tp":           "#3fb950",
    "tp_dim":       "#3fb95015",
    "volume_up":    "#3fb95050",
    "volume_down":  "#f8514950",
    "border":       "#30363d",
}


def _price_label(ax, price: float, label: str, color: str, x_max: int, fmt: str = ",.2f"):
    """Draw a price label box at the right edge of a horizontal line."""
    formatted = f"{price:{fmt}}"
    ax.text(
        x_max - 0.5, price, f" {label}: {formatted} ",
        color=COLORS["bg"], fontsize=7, fontweight="bold",
        va="center", ha="right",
        bbox=dict(
            boxstyle="round,pad=0.2",
            facecolor=color,
            edgecolor="none",
            alpha=0.95,
        ),
        zorder=10,
    )


def create_chart(signal: dict, config: dict) -> io.BytesIO | None:
    """Generate a signal chart PNG and return as BytesIO buffer."""
    chart_cfg = config.get("chart", {})
    width = chart_cfg.get("width", 1200)
    height = chart_cfg.get("height", 900)
    n_candles = chart_cfg.get("candles", 80)
    watermark = chart_cfg.get("watermark", "NPK Sinais")

    df = signal.get("candles_df")
    if df is None or df.empty:
        return None

    df = df.tail(n_candles).copy().reset_index(drop=True)

    fig = plt.figure(figsize=(width / 100, height / 100), dpi=100, facecolor=COLORS["bg"])

    gs = fig.add_gridspec(
        4, 1,
        height_ratios=[5, 1.2, 1.2, 1.2],
        hspace=0.0,
        left=0.06, right=0.97, top=0.93, bottom=0.06,
    )

    ax_price = fig.add_subplot(gs[0])
    ax_vol   = fig.add_subplot(gs[1], sharex=ax_price)
    ax_rsi   = fig.add_subplot(gs[2], sharex=ax_price)
    ax_macd  = fig.add_subplot(gs[3], sharex=ax_price)
    axes = [ax_price, ax_vol, ax_rsi, ax_macd]

    for ax in axes:
        ax.set_facecolor(COLORS["panel"])
        ax.tick_params(colors=COLORS["text_dim"], labelsize=7.5)
        ax.grid(True, color=COLORS["grid"], alpha=0.8, linewidth=0.4)
        for spine in ax.spines.values():
            spine.set_color(COLORS["border"])
            spine.set_linewidth(0.5)

    x = np.arange(len(df))
    x_max = len(df)

    # ─── Candlestick ───────────────────────────────────────────
    for i, row in df.iterrows():
        is_bull = row["close"] >= row["open"]
        color = COLORS["green"] if is_bull else COLORS["red"]
        body_bottom = min(row["open"], row["close"])
        body_height = abs(row["close"] - row["open"])
        if body_height == 0:
            body_height = row["close"] * 0.0001
        ax_price.add_patch(Rectangle(
            (i - 0.38, body_bottom), 0.76, body_height,
            facecolor=color, edgecolor=color, linewidth=0,
        ))
        ax_price.plot([i, i], [row["low"], body_bottom], color=color, linewidth=0.8, zorder=2)
        ax_price.plot([i, i], [body_bottom + body_height, row["high"]], color=color, linewidth=0.8, zorder=2)

    # ─── EMAs ──────────────────────────────────────────────────
    if "ema9" in df.columns:
        ax_price.plot(x, df["ema9"], color=COLORS["orange"], linewidth=1.2, label="EMA 9", alpha=0.9, zorder=3)
    if "ema21" in df.columns:
        ax_price.plot(x, df["ema21"], color=COLORS["purple"], linewidth=1.2, label="EMA 21", alpha=0.9, zorder=3)

    # ─── Bollinger Bands ───────────────────────────────────────
    if "bb_upper" in df.columns:
        ax_price.plot(x, df["bb_upper"], color=COLORS["blue"], linewidth=0.6, alpha=0.35)
        ax_price.plot(x, df["bb_lower"], color=COLORS["blue"], linewidth=0.6, alpha=0.35)
        ax_price.fill_between(x, df["bb_lower"], df["bb_upper"], color=COLORS["blue_dim"], alpha=1)

    # ─── Signal levels ─────────────────────────────────────────
    entry = signal.get("entry")
    sl = signal.get("stop_loss")
    tp1 = signal.get("tp1")
    tp2 = signal.get("tp2")
    tp3 = signal.get("tp3")

    # Risk zone fill
    if entry and sl:
        ax_price.fill_between(x, sl, entry, color=COLORS["sl_dim"], alpha=1, zorder=1)
    # Reward zone fill
    if entry and tp3:
        ax_price.fill_between(x, entry, tp3, color=COLORS["tp_dim"], alpha=1, zorder=1)

    # Entry line
    if entry:
        ax_price.axhline(entry, color=COLORS["entry"], linestyle="--", linewidth=1.4, zorder=4, alpha=0.9)
        _price_label(ax_price, entry, "ENTRY", COLORS["entry"], x_max)

    # SL line
    if sl:
        ax_price.axhline(sl, color=COLORS["sl"], linestyle="--", linewidth=1.2, zorder=4, alpha=0.85)
        _price_label(ax_price, sl, "SL", COLORS["sl"], x_max)

    # TP lines
    if tp1:
        ax_price.axhline(tp1, color=COLORS["tp"], linestyle=":", linewidth=0.9, zorder=4, alpha=0.6)
        _price_label(ax_price, tp1, "TP1", COLORS["tp"], x_max)
    if tp2:
        ax_price.axhline(tp2, color=COLORS["tp"], linestyle=":", linewidth=1.0, zorder=4, alpha=0.75)
        _price_label(ax_price, tp2, "TP2", COLORS["tp"], x_max)
    if tp3:
        ax_price.axhline(tp3, color=COLORS["tp"], linestyle=":", linewidth=1.1, zorder=4, alpha=0.9)
        _price_label(ax_price, tp3, "TP3", COLORS["tp"], x_max)

    # ─── Title ─────────────────────────────────────────────────
    pair = signal.get("pair", "")
    direction = signal.get("direction", "")
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio", 0)
    score = signal.get("score", 0)
    tf = signal.get("timeframe", "1H")
    dir_arrow = "▲" if direction == "LONG" else "▼"
    dir_color = COLORS["green"] if direction == "LONG" else COLORS["red"]

    fig.text(
        0.06, 0.965,
        f"{pair}  {tf}",
        color=COLORS["text"], fontsize=13, fontweight="bold",
        va="top", ha="left",
    )
    fig.text(
        0.22, 0.965,
        f"{dir_arrow} {direction}",
        color=dir_color, fontsize=13, fontweight="bold",
        va="top", ha="left",
    )
    fig.text(
        0.35, 0.965,
        f"Confiança {confidence}%  •  R:R {rr}:1  •  Score {score:.0f}/6",
        color=COLORS["text_dim"], fontsize=9,
        va="top", ha="left",
    )

    # Legend
    ax_price.legend(
        loc="upper left", fontsize=7.5,
        facecolor=COLORS["panel2"], edgecolor=COLORS["border"],
        labelcolor=COLORS["text_dim"], framealpha=0.85,
    )

    # Watermark
    if watermark:
        ax_price.text(
            0.5, 0.5, watermark,
            transform=ax_price.transAxes,
            fontsize=32, color=COLORS["text"], alpha=0.04,
            ha="center", va="center", fontweight="bold",
            rotation=0,
        )
        fig.text(
            0.97, 0.01, watermark,
            color=COLORS["text_dim"], fontsize=8, alpha=0.5,
            ha="right", va="bottom",
        )

    # ─── Volume ───────────────────────────────────────────────
    vol_colors = [
        COLORS["volume_up"] if df["close"].iloc[i] >= df["open"].iloc[i]
        else COLORS["volume_down"]
        for i in range(len(df))
    ]
    ax_vol.bar(x, df["volume"], color=vol_colors, width=0.7)
    ax_vol.set_ylabel("VOL", color=COLORS["text_dim"], fontsize=7, labelpad=4)
    ax_vol.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v/1e6:.1f}M" if v >= 1e6 else f"{v/1e3:.0f}K"))

    # ─── RSI ──────────────────────────────────────────────────
    if "rsi" in df.columns:
        rsi = df["rsi"]
        ax_rsi.plot(x, rsi, color=COLORS["blue"], linewidth=1, zorder=3)
        ax_rsi.axhline(70, color=COLORS["red"], linewidth=0.5, linestyle="--", alpha=0.6)
        ax_rsi.axhline(30, color=COLORS["green"], linewidth=0.5, linestyle="--", alpha=0.6)
        ax_rsi.axhline(50, color=COLORS["text_dim"], linewidth=0.3, linestyle=":", alpha=0.4)
        ax_rsi.fill_between(x, rsi, 70, where=(rsi >= 70), color=COLORS["red_dim"], alpha=1)
        ax_rsi.fill_between(x, rsi, 30, where=(rsi <= 30), color=COLORS["green_dim"], alpha=1)
        ax_rsi.set_ylim(0, 100)
        ax_rsi.set_yticks([30, 50, 70])
    ax_rsi.set_ylabel("RSI", color=COLORS["text_dim"], fontsize=7, labelpad=4)

    # ─── MACD ─────────────────────────────────────────────────
    if "macd" in df.columns:
        ax_macd.plot(x, df["macd"], color=COLORS["blue"], linewidth=1, label="MACD", zorder=3)
        ax_macd.plot(x, df["macd_signal"], color=COLORS["orange"], linewidth=1, label="Signal", zorder=3)
        hist = df["macd_hist"]
        hist_colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in hist]
        ax_macd.bar(x, hist, color=hist_colors, width=0.7, alpha=0.6)
        ax_macd.axhline(0, color=COLORS["text_dim"], linewidth=0.4, alpha=0.5)
    ax_macd.set_ylabel("MACD", color=COLORS["text_dim"], fontsize=7, labelpad=4)

    # ─── X-axis labels (only on bottom) ───────────────────────
    for ax in [ax_price, ax_vol, ax_rsi]:
        plt.setp(ax.get_xticklabels(), visible=False)

    ax_macd.set_xlim(-0.5, len(df) - 0.5)

    # Timestamp labels on MACD axis
    if "datetime" in df.columns:
        step = max(1, len(df) // 8)
        tick_positions = x[::step]
        tick_labels = [df["datetime"].iloc[i].strftime("%m/%d %H:%M") for i in tick_positions]
        ax_macd.set_xticks(tick_positions)
        ax_macd.set_xticklabels(tick_labels, fontsize=6.5, color=COLORS["text_dim"], rotation=20, ha="right")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=COLORS["bg"], bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf


def create_pnl_chart(trades: list, config: dict) -> io.BytesIO:
    """Generate an equity curve chart from trade history."""
    chart_cfg = config.get("chart", {})
    watermark = chart_cfg.get("watermark", "NPK Sinais")

    pnl_values = [t["pnl_pct"] for t in trades]
    cumulative = list(np.cumsum(pnl_values))

    fig, axes = plt.subplots(
        2, 1, figsize=(12, 7), dpi=100, facecolor=COLORS["bg"],
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
    )
    ax, ax_bar = axes

    for a in axes:
        a.set_facecolor(COLORS["panel"])
        a.tick_params(colors=COLORS["text_dim"], labelsize=8)
        a.grid(True, color=COLORS["grid"], alpha=0.8, linewidth=0.4)
        for spine in a.spines.values():
            spine.set_color(COLORS["border"])
            spine.set_linewidth(0.5)

    x = np.arange(1, len(cumulative) + 1)

    # Equity curve
    ax.fill_between(x, cumulative, 0,
                    where=[v >= 0 for v in cumulative],
                    color=COLORS["green_dim"], alpha=1, interpolate=True)
    ax.fill_between(x, cumulative, 0,
                    where=[v < 0 for v in cumulative],
                    color=COLORS["red_dim"], alpha=1, interpolate=True)
    ax.plot(x, cumulative, color=COLORS["blue"], linewidth=2, zorder=4)
    ax.axhline(0, color=COLORS["text_dim"], linewidth=0.5, alpha=0.5)

    # Trade dots
    for i, val in enumerate(cumulative):
        color = COLORS["green"] if pnl_values[i] >= 0 else COLORS["red"]
        ax.scatter(i + 1, val, color=color, s=35, zorder=5, edgecolors="none")

    # Individual bars
    bar_colors = [COLORS["green"] if p >= 0 else COLORS["red"] for p in pnl_values]
    ax_bar.bar(x, pnl_values, color=bar_colors, width=0.7, alpha=0.8)
    ax_bar.axhline(0, color=COLORS["text_dim"], linewidth=0.5, alpha=0.5)
    ax_bar.set_ylabel("PNL %", color=COLORS["text_dim"], fontsize=8)

    total_pnl = cumulative[-1] if cumulative else 0
    wins = sum(1 for p in pnl_values if p > 0)
    wr = (wins / len(pnl_values) * 100) if pnl_values else 0
    total_trades = len(pnl_values)
    pnl_str = f"+{total_pnl:.1f}%" if total_pnl >= 0 else f"{total_pnl:.1f}%"

    fig.text(0.05, 0.97, "Equity Curve", color=COLORS["text"], fontsize=13, fontweight="bold", va="top")
    fig.text(
        0.05, 0.93,
        f"{total_trades} trades  •  PNL {pnl_str}  •  Win Rate {wr:.0f}%",
        color=COLORS["text_dim"], fontsize=9, va="top",
    )

    ax.set_ylabel("PNL Acumulado %", color=COLORS["text_dim"], fontsize=8)
    ax.set_xlim(0.5, len(cumulative) + 0.5)
    ax_bar.set_xlim(0.5, len(cumulative) + 0.5)

    if watermark:
        ax.text(0.5, 0.5, watermark, transform=ax.transAxes,
                fontsize=28, color=COLORS["text"], alpha=0.04,
                ha="center", va="center", fontweight="bold")
        fig.text(0.97, 0.01, watermark, color=COLORS["text_dim"], fontsize=8, alpha=0.4, ha="right", va="bottom")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=COLORS["bg"], bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf
