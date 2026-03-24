"""
Chart Generator — sideradogcripto cyberpunk theme.
Neon glow, dark bg, minimal clutter. Built to impress.
"""

import io
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.ticker import FuncFormatter
from datetime import datetime, timezone


# ── Cyberpunk palette ──────────────────────────────────────────────────────
C = {
    "bg":           "#07090f",
    "panel":        "#0b0e18",
    "panel2":       "#0f1220",
    "grid":         "#121828",
    "border":       "#1e2a45",

    # Neon cores
    "cyan":         "#00e5ff",
    "cyan_dim":     "#00e5ff18",
    "magenta":      "#ff0066",
    "magenta_dim":  "#ff006618",
    "green":        "#00ff88",
    "green_dim":    "#00ff8818",
    "green_bright": "#39ff14",
    "purple":       "#b44fff",
    "purple_dim":   "#b44fff20",
    "orange":       "#ff8800",
    "yellow":       "#ffe600",

    # Candles
    "bull":         "#00ff88",
    "bull_dim":     "#00ff8840",
    "bear":         "#ff0066",
    "bear_dim":     "#ff006640",

    # Sinais
    "entry":        "#00e5ff",
    "sl":           "#ff0066",
    "tp1":          "#00ff88",
    "tp2":          "#39ff14",
    "tp3":          "#ffe600",

    # Texto
    "text":         "#c8d8f0",
    "text_dim":     "#4a6080",

    # Volume
    "vol_up":       "#00ff8828",
    "vol_dn":       "#ff006628",
}


def _glow(ax, x, y, color, lw=1.5, alpha=0.9, layers=3):
    """Simula efeito neon glow plotando camadas."""
    for i in range(layers, 0, -1):
        ax.plot(x, y,
                color=color,
                linewidth=lw * (1 + i * 0.8),
                alpha=alpha * (0.15 / i),
                zorder=2)
    ax.plot(x, y, color=color, linewidth=lw, alpha=alpha, zorder=3)


def _hline_glow(ax, price, color, lw=1.2, style="--", alpha=0.9):
    """Linha horizontal com glow neon."""
    ax.axhline(price, color=color, linewidth=lw * 3, alpha=0.08, zorder=3)
    ax.axhline(price, color=color, linewidth=lw * 1.5, alpha=0.2, zorder=4)
    ax.axhline(price, color=color, linewidth=lw, linestyle=style, alpha=alpha, zorder=5)


def _price_tag(ax, price, label, color, x_max, fmt=",.2f"):
    """Tag de preço minimalista — sem box, só texto neon."""
    ax.text(
        x_max - 0.3, price,
        f"{label} {price:{fmt}}",
        color=color, fontsize=6.8, fontweight="bold",
        va="center", ha="right", zorder=10,
        path_effects=[pe.withStroke(linewidth=3, foreground=C["bg"])],
    )


def _pick_fmt(price: float) -> str:
    if price >= 1000: return ",.1f"
    if price >= 10:   return ",.3f"
    if price >= 1:    return ",.4f"
    return ",.6f"


def create_chart(signal: dict, config: dict) -> io.BytesIO | None:
    chart_cfg = config.get("chart", {})
    n_candles = chart_cfg.get("candles", 80)

    df = signal.get("candles_df")
    if df is None or df.empty:
        return None

    df = df.tail(n_candles).copy().reset_index(drop=True)

    fig = plt.figure(
        figsize=(12, 7), dpi=100,
        facecolor=C["bg"],
    )

    gs = fig.add_gridspec(
        3, 1,
        height_ratios=[6, 0.8, 1.4],
        hspace=0.0,
        left=0.04, right=0.93, top=0.88, bottom=0.08,
    )

    ax_p  = fig.add_subplot(gs[0])
    ax_v  = fig.add_subplot(gs[1], sharex=ax_p)
    ax_r  = fig.add_subplot(gs[2], sharex=ax_p)
    axes  = [ax_p, ax_v, ax_r]

    for ax in axes:
        ax.set_facecolor(C["panel"])
        ax.tick_params(colors=C["text_dim"], labelsize=6.5, length=2)
        ax.grid(True, color=C["grid"], alpha=1.0, linewidth=0.4, linestyle="-")
        for spine in ax.spines.values():
            spine.set_color(C["border"])
            spine.set_linewidth(0.8)

    x     = np.arange(len(df))
    x_max = len(df)

    # ── Candles ──────────────────────────────────────────────────────────
    for i, row in df.iterrows():
        bull = row["close"] >= row["open"]
        body_color = C["bull"] if bull else C["bear"]
        dim_color  = C["bull_dim"] if bull else C["bear_dim"]

        lo = min(row["open"], row["close"])
        hi = abs(row["close"] - row["open"]) or row["close"] * 0.0001

        ax_p.add_patch(Rectangle(
            (i - 0.38, lo), 0.76, hi,
            facecolor=body_color, edgecolor=body_color,
            linewidth=0.4, alpha=0.9, zorder=4,
        ))
        # Mecha
        ax_p.plot([i, i], [row["low"], lo],
                  color=body_color, linewidth=0.7, alpha=0.8, zorder=3)
        ax_p.plot([i, i], [lo + hi, row["high"]],
                  color=body_color, linewidth=0.7, alpha=0.8, zorder=3)

    # ── EMAs ─────────────────────────────────────────────────────────────
    if "ema9" in df.columns:
        _glow(ax_p, x, df["ema9"].values, C["cyan"], lw=1.2, alpha=0.8)
    if "ema21" in df.columns:
        _glow(ax_p, x, df["ema21"].values, C["purple"], lw=1.2, alpha=0.8)

    # ── Níveis do sinal ───────────────────────────────────────────────────
    entry = signal.get("entry")
    sl    = signal.get("stop_loss")
    tp1   = signal.get("tp1")
    tp2   = signal.get("tp2")
    tp3   = signal.get("tp3")
    fmt   = _pick_fmt(entry or 1)

    if sl:
        # Zona SL fill
        ax_p.axhspan(sl, sl * (1 - 0.001), alpha=0.12, color=C["sl"], zorder=2)
        _hline_glow(ax_p, sl, C["sl"], lw=1.0, style="--")
        _price_tag(ax_p, sl, "SL", C["sl"], x_max, fmt)

    if entry:
        _hline_glow(ax_p, entry, C["entry"], lw=1.4, style="-")
        _price_tag(ax_p, entry, "ENTRY", C["entry"], x_max, fmt)

    if tp1:
        _hline_glow(ax_p, tp1, C["tp1"], lw=0.9, style="-")
        _price_tag(ax_p, tp1, "TP1", C["tp1"], x_max, fmt)
    if tp2:
        _hline_glow(ax_p, tp2, C["tp2"], lw=1.0, style="-")
        _price_tag(ax_p, tp2, "TP2", C["tp2"], x_max, fmt)
    if tp3:
        # TP3 mais brilhante
        _hline_glow(ax_p, tp3, C["tp3"], lw=1.3, style="-", alpha=1.0)
        _price_tag(ax_p, tp3, "TP3", C["tp3"], x_max, fmt)

    # ── Zona de risco/reward (fill entre SL e TP3) ────────────────────────
    if entry and sl and tp3:
        ax_p.fill_between([0, x_max], sl, entry,
                          color=C["sl"], alpha=0.04, zorder=1)
        ax_p.fill_between([0, x_max], entry, tp3,
                          color=C["green"], alpha=0.04, zorder=1)

    # ── Volume ────────────────────────────────────────────────────────────
    vol_colors = [C["vol_up"] if df["close"].iloc[i] >= df["open"].iloc[i]
                  else C["vol_dn"] for i in range(len(df))]
    ax_v.bar(x, df["volume"], color=vol_colors, width=0.8)
    ax_v.set_yticks([])
    ax_v.text(0.008, 0.75, "VOL", transform=ax_v.transAxes,
              color=C["text_dim"], fontsize=5.5)

    # ── RSI ───────────────────────────────────────────────────────────────
    if "rsi" in df.columns:
        rsi = df["rsi"]
        _glow(ax_r, x, rsi.values, C["purple"], lw=1.2, alpha=0.9, layers=2)
        ax_r.axhline(70, color=C["magenta"], lw=0.5, ls="--", alpha=0.4)
        ax_r.axhline(30, color=C["green"],   lw=0.5, ls="--", alpha=0.4)
        ax_r.axhline(50, color=C["text_dim"], lw=0.3, ls=":", alpha=0.25)
        ax_r.fill_between(x, rsi, 70, where=(rsi >= 70),
                          color=C["magenta"], alpha=0.12)
        ax_r.fill_between(x, rsi, 30, where=(rsi <= 30),
                          color=C["green"], alpha=0.12)
        ax_r.set_ylim(10, 90)
        ax_r.set_yticks([30, 50, 70])
        ax_r.tick_params(labelsize=5.5)
    ax_r.text(0.008, 0.75, "RSI", transform=ax_r.transAxes,
              color=C["text_dim"], fontsize=5.5)

    # ── X-axis timestamps ─────────────────────────────────────────────────
    for ax in [ax_p, ax_v]:
        plt.setp(ax.get_xticklabels(), visible=False)
    ax_r.set_xlim(-0.5, len(df) - 0.5)

    if "datetime" in df.columns:
        step   = max(1, len(df) // 6)
        ticks  = x[::step]
        labels = [df["datetime"].iloc[i].strftime("%d/%m %H:%M") for i in ticks]
        ax_r.set_xticks(ticks)
        ax_r.set_xticklabels(labels, fontsize=5.5, color=C["text_dim"],
                             rotation=15, ha="right")

    # ── Header ────────────────────────────────────────────────────────────
    pair      = signal.get("pair", "")
    direction = signal.get("direction", "")
    conf      = signal.get("confidence", 0)
    rr        = signal.get("rr_ratio", 0)
    tf        = signal.get("timeframe", "1H").upper()

    dir_color = C["green"] if direction == "LONG" else C["magenta"]
    dir_sym   = "▲ LONG" if direction == "LONG" else "▼ SHORT"

    # Pair
    fig.text(0.04, 0.965, pair,
             color=C["cyan"], fontsize=15, fontweight="bold", va="top",
             path_effects=[pe.withStroke(linewidth=4, foreground=C["bg"])])
    fig.text(0.04 + len(pair) * 0.013, 0.965, f"  {tf}",
             color=C["text_dim"], fontsize=10, va="top")

    # Direction
    fig.text(0.42, 0.965, dir_sym,
             color=dir_color, fontsize=13, fontweight="bold", va="top",
             path_effects=[pe.withStroke(linewidth=3, foreground=C["bg"])])

    # Stats — minimal
    fig.text(0.62, 0.965, f"CONF {conf}%  ·  R:R {rr}:1",
             color=C["text_dim"], fontsize=8.5, va="top")

    # ── Watermark ─────────────────────────────────────────────────────────
    ax_p.text(0.5, 0.5, "SIDERADOG",
              transform=ax_p.transAxes,
              fontsize=52, color=C["cyan"], alpha=0.025,
              ha="center", va="center", fontweight="bold",
              path_effects=[pe.withStroke(linewidth=1, foreground=C["cyan"])])

    # Brand tag bottom-right
    fig.text(0.93, 0.012, "⚡ sideradogcripto",
             color=C["cyan"], fontsize=7.5, alpha=0.5,
             ha="right", va="bottom", fontweight="bold")

    # Linha decorativa topo (neon)
    fig.add_artist(plt.Line2D(
        [0.04, 0.96], [0.945, 0.945],
        transform=fig.transFigure,
        color=C["cyan"], linewidth=0.6, alpha=0.35,
    ))

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=C["bg"],
                bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Equity curve ──────────────────────────────────────────────────────────

def create_pnl_chart(trades: list, config: dict) -> io.BytesIO:
    pnl_values = [t["pnl_pct"] for t in trades]
    cumulative = list(np.cumsum(pnl_values))

    fig, (ax, ax_bar) = plt.subplots(
        2, 1, figsize=(12, 6.5), dpi=100, facecolor=C["bg"],
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.06},
    )

    for a in [ax, ax_bar]:
        a.set_facecolor(C["panel"])
        a.tick_params(colors=C["text_dim"], labelsize=7, length=2)
        a.grid(True, color=C["grid"], alpha=1.0, linewidth=0.4)
        for spine in a.spines.values():
            spine.set_color(C["border"])
            spine.set_linewidth(0.7)

    x = np.arange(1, len(cumulative) + 1)

    # Fill verde/vermelho
    ax.fill_between(x, cumulative, 0,
                    where=[v >= 0 for v in cumulative],
                    color=C["green"], alpha=0.08, interpolate=True)
    ax.fill_between(x, cumulative, 0,
                    where=[v < 0 for v in cumulative],
                    color=C["magenta"], alpha=0.08, interpolate=True)

    # Linha principal com glow
    _glow(ax, x, cumulative, C["cyan"], lw=2.0, alpha=1.0, layers=3)
    ax.axhline(0, color=C["text_dim"], linewidth=0.5, alpha=0.4)

    # Pontos
    for i, val in enumerate(cumulative):
        col = C["green"] if pnl_values[i] >= 0 else C["magenta"]
        ax.scatter(i + 1, val, color=col, s=28, zorder=6, edgecolors="none")

    # Barras
    bar_colors = [C["green"] if p >= 0 else C["magenta"] for p in pnl_values]
    ax_bar.bar(x, pnl_values, color=bar_colors, width=0.65, alpha=0.75)
    ax_bar.axhline(0, color=C["text_dim"], linewidth=0.4, alpha=0.4)
    ax_bar.set_yticks([])

    total  = cumulative[-1] if cumulative else 0
    wins   = sum(1 for p in pnl_values if p > 0)
    wr     = (wins / len(pnl_values) * 100) if pnl_values else 0
    n      = len(pnl_values)
    t_str  = f"+{total:.1f}%" if total >= 0 else f"{total:.1f}%"
    t_col  = C["green"] if total >= 0 else C["magenta"]

    # Header
    fig.text(0.04, 0.97, "EQUITY CURVE",
             color=C["cyan"], fontsize=13, fontweight="bold", va="top",
             path_effects=[pe.withStroke(linewidth=3, foreground=C["bg"])])
    fig.text(0.04, 0.93,
             f"{n} trades  ·  {wr:.0f}% acerto",
             color=C["text_dim"], fontsize=8.5, va="top")
    fig.text(0.93, 0.97, t_str,
             color=t_col, fontsize=14, fontweight="bold", va="top", ha="right",
             path_effects=[pe.withStroke(linewidth=3, foreground=C["bg"])])

    # Watermark
    ax.text(0.5, 0.5, "SIDERADOG",
            transform=ax.transAxes,
            fontsize=48, color=C["cyan"], alpha=0.025,
            ha="center", va="center", fontweight="bold")

    fig.text(0.96, 0.012, "⚡ sideradogcripto",
             color=C["cyan"], fontsize=7.5, alpha=0.5,
             ha="right", va="bottom", fontweight="bold")

    fig.add_artist(plt.Line2D(
        [0.04, 0.96], [0.91, 0.91],
        transform=fig.transFigure,
        color=C["cyan"], linewidth=0.5, alpha=0.3,
    ))

    ax.set_xlim(0.5, len(cumulative) + 0.5)
    ax_bar.set_xlim(0.5, len(cumulative) + 0.5)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=C["bg"],
                bbox_inches="tight", dpi=100)
    plt.close(fig)
    buf.seek(0)
    return buf
