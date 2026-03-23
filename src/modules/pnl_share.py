"""
PNL Share Card — card visual de resultado de trade para compartilhar.
Design premium dark, estilo trading card profissional.
"""

import io
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch
import matplotlib.patheffects as pe
import numpy as np


# ── Palette ────────────────────────────────────────────────────────────────
BG      = "#0a0e17"
BG2     = "#0f1520"
BG3     = "#151d2e"
PANEL   = "#1a2236"
BORDER  = "#1e2d45"
ACCENT  = "#00d4aa"
GREEN   = "#00e676"
RED     = "#ff3d57"
YELLOW  = "#ffd740"
WHITE   = "#e8eef6"
GRAY    = "#6b7a99"
GRAY2   = "#2a3652"
TEAL    = "#00b8d9"


def _fmt_price(price: float) -> str:
    if not price:
        return "—"
    if price >= 10000:
        return f"{price:,.1f}"
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 100:
        return f"{price:,.3f}"
    if price >= 1:
        return f"{price:,.4f}"
    return f"{price:,.6f}"


def _duration(opened_at: str, closed_at: str) -> str:
    try:
        a = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
        b = datetime.fromisoformat(closed_at.replace("Z", "+00:00"))
        secs = (b - a).total_seconds()
        if secs >= 86400:
            d = int(secs // 86400)
            h = int((secs % 86400) // 3600)
            return f"{d}d {h}h"
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        return f"{h}h {m}m" if h else f"{m}m"
    except Exception:
        return "—"


def _round_rect(ax, x, y, w, h, r=0.1, **kw):
    bp = FancyBboxPatch((x, y), w, h,
                        boxstyle=f"round,pad=0",
                        linewidth=0, **kw)
    ax.add_patch(bp)


def create_pnl_share(trade: dict, stats: dict = None,
                     bankroll: float = 1000.0,
                     ref_link: str = "") -> io.BytesIO:
    """Gera card de resultado de trade estilo premium para compartilhar."""
    from modules.performance import PerformanceDB

    # ── Trade data ──────────────────────────────────────────────────────────
    pair       = trade.get("pair", "—")
    direction  = trade.get("direction", "LONG")
    entry      = float(trade.get("entry", 0) or 0)
    sl         = float(trade.get("stop_loss", 0) or 0)
    tp1        = float(trade.get("tp1", 0) or 0)
    tp2        = float(trade.get("tp2", 0) or 0)
    tp3        = float(trade.get("tp3", 0) or 0)
    exit_price = float(trade.get("exit_price", 0) or 0)
    tp1_hit    = bool(trade.get("tp1_hit"))
    tp2_hit    = bool(trade.get("tp2_hit"))
    tp3_hit    = bool(trade.get("tp3_hit"))
    sl_hit     = bool(trade.get("sl_hit"))
    risk_pct   = float(trade.get("risk_pct", 2.0) or 2.0)
    confidence = int(trade.get("confidence", 0) or 0)
    opened_at  = trade.get("opened_at", "")
    closed_at  = trade.get("closed_at", "")

    risk_usd  = bankroll * risk_pct / 100
    sl_dist   = abs(entry - sl)
    sl_pct    = sl_dist / entry * 100 if entry else 0
    size_usd  = risk_usd / (sl_pct / 100) if sl_pct else 0
    pnl_usd   = PerformanceDB.calc_pnl_usd(trade, bankroll)
    pnl_banca = (pnl_usd / bankroll * 100) if bankroll else 0

    # R:R real obtido (do entry ao exit)
    if exit_price and sl_dist:
        if direction == "LONG":
            rr_achieved = (exit_price - entry) / sl_dist
        else:
            rr_achieved = (entry - exit_price) / sl_dist
    else:
        rr_achieved = float(trade.get("rr_ratio", 0) or 0)

    # R:R planejado máximo (TP3)
    rr_planned = abs(tp3 - entry) / sl_dist if sl_dist and tp3 else 0

    last_tp = ("TP3" if tp3_hit else
               "TP2" if tp2_hit else
               "TP1" if tp1_hit else
               "STOP" if sl_hit else "—")

    duration = _duration(opened_at, closed_at)
    is_win   = pnl_usd >= 0
    color_r  = GREEN if is_win else RED
    color_d  = ACCENT if direction == "LONG" else RED

    # Stats
    s_total  = stats.get("total_trades", 0) if stats else 0
    s_wr     = stats.get("win_rate", 0.0) if stats else 0.0
    s_pf     = stats.get("profit_factor", 0.0) if stats else 0.0
    s_pnl    = stats.get("total_pnl_usd", 0.0) if stats else 0.0

    # ── Canvas ─────────────────────────────────────────────────────────────
    W, H = 14.0, 7.875   # 1400×787px @ 100dpi (16:9)
    fig  = plt.figure(figsize=(W, H), facecolor=BG)
    ax   = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")

    # ── Background layers ───────────────────────────────────────────────────
    ax.add_patch(patches.Rectangle((0, 0), W, H, color=BG, zorder=0))

    # Grid dots (subtle)
    for xi in np.arange(0.5, W, 0.7):
        for yi in np.arange(0.5, H, 0.7):
            ax.plot(xi, yi, ".", color=BORDER, markersize=1, alpha=0.4, zorder=0)

    # Left accent column
    ax.add_patch(patches.Rectangle((0, 0), 0.25, H, color=ACCENT if is_win else RED, zorder=1))

    # Top bar
    ax.add_patch(patches.Rectangle((0.25, H - 0.06), W, 0.06, color=ACCENT if is_win else RED, alpha=0.8, zorder=1))

    # Header panel
    ax.add_patch(patches.Rectangle((0.25, H - 1.45), W, 1.39, color=BG2, zorder=1))

    # Center card (main content)
    ax.add_patch(patches.Rectangle((0.25, 1.25), W - 0.25, H - 2.85, color=BG3, alpha=0.6, zorder=1))

    # Footer panel
    ax.add_patch(patches.Rectangle((0.25, 0), W - 0.25, 1.25, color=BG2, zorder=1))

    # Separator lines
    for y in [H - 1.45, 1.25]:
        ax.plot([0.25, W], [y, y], color=BORDER, linewidth=0.8, zorder=2)

    # ── RESULT GLOW (behind PNL number) ────────────────────────────────────
    glow_x = W * 0.38
    glow_y = H - 1.45 - 1.65
    for r, alpha in [(2.5, 0.03), (1.8, 0.05), (1.2, 0.07)]:
        ax.add_patch(plt.Circle((glow_x, glow_y), r,
                                color=color_r, alpha=alpha, zorder=1))

    # ── HEADER ─────────────────────────────────────────────────────────────
    # Branding
    ax.text(0.7, H - 0.55, "NPK SINAIS", color=ACCENT, fontsize=13,
            fontweight="bold", va="center", fontfamily="monospace", zorder=3)
    ax.text(0.7, H - 0.95, "Signal Intelligence • BloFin Futures", color=GRAY,
            fontsize=8.5, va="center", fontfamily="monospace", zorder=3)

    # Pair
    ax.text(W * 0.42, H - 0.52, pair, color=WHITE, fontsize=26,
            fontweight="bold", va="center", ha="center", zorder=3)

    dir_symbol = "▲ LONG" if direction == "LONG" else "▼ SHORT"
    ax.text(W * 0.42, H - 1.0, dir_symbol, color=color_d, fontsize=12,
            fontweight="bold", va="center", ha="center", zorder=3)

    # Result badge
    badge_w, badge_h = 2.4, 0.58
    badge_x = W - badge_w - 0.5
    badge_y = H - 1.22
    _round_rect(ax, badge_x, badge_y, badge_w, badge_h,
                facecolor=color_r + "25", edgecolor=color_r, linewidth=2, zorder=2)
    badge_text = f"✓  LUCRO" if is_win else "✗  LOSS"
    ax.text(badge_x + badge_w / 2, badge_y + badge_h / 2, badge_text,
            color=color_r, fontsize=12, fontweight="bold",
            va="center", ha="center", zorder=3)

    # ── PNL PRINCIPAL ──────────────────────────────────────────────────────
    pnl_sign = "+" if pnl_usd >= 0 else ""
    pnl_str  = f"{pnl_sign}${pnl_usd:.2f}"
    pnl_text = ax.text(W * 0.38, H - 2.45, pnl_str,
                       color=color_r, fontsize=52, fontweight="bold",
                       va="center", ha="center", fontfamily="monospace", zorder=3)
    pnl_text.set_path_effects([
        pe.withStroke(linewidth=8, foreground=color_r + "22"),
    ])

    pct_sign = "+" if pnl_banca >= 0 else ""
    ax.text(W * 0.38, H - 3.2,
            f"{pct_sign}{pnl_banca:.2f}% da banca   •   R:R obtido  {rr_achieved:.2f}:1",
            color=GRAY, fontsize=10, va="center", ha="center", zorder=3)

    # ── METRICS COLUMN (right of PNL) ──────────────────────────────────────
    mx = W * 0.72
    metrics = [
        ("RISCO",     f"${risk_usd:.2f}",  GRAY),
        ("SIZE",      f"${size_usd:,.0f}", WHITE),
        ("CONFIANÇA", f"{confidence}%",    ACCENT),
        ("DURAÇÃO",   duration,            GRAY),
        ("ENCERROU",  last_tp,             color_r),
    ]
    for i, (lbl, val, vc) in enumerate(metrics):
        y = H - 1.85 - i * 0.58
        ax.text(mx - 0.15, y, lbl, color=GRAY, fontsize=7.5,
                va="center", ha="right", fontfamily="monospace", zorder=3)
        ax.text(mx + 0.05, y, val, color=vc, fontsize=10,
                fontweight="bold", va="center", ha="left", fontfamily="monospace", zorder=3)

    # Vertical separator
    sep_x = W * 0.60
    ax.plot([sep_x, sep_x], [H - 1.5, 1.35], color=BORDER, linewidth=0.8, zorder=2)

    # ── PRICE LEVEL BAR ────────────────────────────────────────────────────
    bar_y  = 1.82
    bar_x0 = 0.55
    bar_x1 = sep_x - 0.3

    # Determine scale
    all_prices = [p for p in [sl, entry, tp1, tp2, tp3] if p]
    if all_prices:
        p_min = min(all_prices)
        p_max = max(all_prices)
        p_range = p_max - p_min or 1.0

        def px(p):
            return bar_x0 + (p - p_min) / p_range * (bar_x1 - bar_x0)

        # Background rail
        ax.add_patch(patches.Rectangle((bar_x0, bar_y - 0.055),
                                       bar_x1 - bar_x0, 0.11,
                                       color=GRAY2, zorder=2, linewidth=0))

        # Filled zone (entry → exit/last hit)
        ref_exit = exit_price or (tp1 if tp1_hit else entry)
        fx0 = min(px(entry), px(ref_exit))
        fx1 = max(px(entry), px(ref_exit))
        ax.add_patch(patches.Rectangle((fx0, bar_y - 0.055),
                                       fx1 - fx0, 0.11,
                                       color=color_r, alpha=0.7, zorder=3))

        # Level markers
        levels_def = [
            (sl,    "SL",   RED,    sl_hit,  -0.3),
            (entry, "ENT",  WHITE,  True,     0.0),
            (tp1,   "TP1",  TEAL,   tp1_hit,  0.0),
            (tp2,   "TP2",  TEAL,   tp2_hit,  0.0),
            (tp3,   "TP3",  ACCENT, tp3_hit,  0.0),
        ]
        for price, label, mc, hit, _ in levels_def:
            if not price:
                continue
            x    = px(price)
            col  = mc if hit else GRAY
            tick_h = 0.22
            ax.plot([x, x], [bar_y - tick_h, bar_y + tick_h],
                    color=col, linewidth=2.5, zorder=4)
            check = "✓" if hit and label not in ("ENT",) else ""
            ax.text(x, bar_y + tick_h + 0.08, f"{label}{check}",
                    color=col, fontsize=7.5, ha="center", va="bottom",
                    fontweight="bold", zorder=5)
            ax.text(x, bar_y - tick_h - 0.08, _fmt_price(price),
                    color=col, fontsize=6.8, ha="center", va="top",
                    fontfamily="monospace", zorder=5)

    # Level bar label
    ax.text(bar_x0, bar_y + 0.55, "NÍVEIS DE PREÇO", color=GRAY,
            fontsize=7, va="center", fontfamily="monospace", zorder=3)

    # ── ENTRY / EXIT DETAIL ─────────────────────────────────────────────────
    detail_y = 1.45
    pairs_d = [
        ("ENTRADA",  _fmt_price(entry),      WHITE),
        ("SAÍDA",    _fmt_price(exit_price),  color_r),
        ("R:R PLAN.",f"{rr_planned:.2f}:1",  GRAY),
        ("R:R REAL", f"{rr_achieved:.2f}:1", color_r),
    ]
    col_w = (sep_x - 0.55) / len(pairs_d)
    for i, (lbl, val, vc) in enumerate(pairs_d):
        x = 0.55 + col_w * (i + 0.5)
        ax.text(x, detail_y + 0.18, lbl, color=GRAY, fontsize=7,
                ha="center", va="center", fontfamily="monospace", zorder=3)
        ax.text(x, detail_y - 0.08, val, color=vc, fontsize=9.5,
                ha="center", va="center", fontweight="bold",
                fontfamily="monospace", zorder=3)

    # ── FOOTER — global stats ───────────────────────────────────────────────
    if s_total > 0:
        stats_items = [
            ("WIN RATE",     f"{s_wr:.1f}%",   s_wr >= 50),
            ("PROFIT FACTOR",f"{s_pf:.2f}x",   s_pf >= 1.0),
            ("TOTAL TRADES", f"{s_total}",      True),
            ("PNL TOTAL",    f"${s_pnl:+.2f}", s_pnl >= 0),
        ]
        col_w2 = (W - 0.5) / len(stats_items)
        for i, (lbl, val, pos) in enumerate(stats_items):
            x = 0.35 + col_w2 * (i + 0.5)
            vc = GREEN if pos else RED
            ax.text(x, 0.95, lbl, color=GRAY, fontsize=7.2, ha="center",
                    va="center", fontfamily="monospace", zorder=3)
            ax.text(x, 0.52, val, color=vc, fontsize=12, ha="center",
                    fontweight="bold", va="center", fontfamily="monospace", zorder=3)

        # Separator above stats
        ax.plot([0.35, W - 0.1], [1.22, 1.22], color=BORDER, linewidth=0.5, zorder=2)

    # Brand
    brand_y = 0.18
    ax.text(W * 0.5, brand_y,
            "NPK Sinais  •  Resultados reais, risco gerenciado",
            color=GRAY, fontsize=8, ha="center", va="center",
            fontfamily="monospace", alpha=0.7, zorder=3)

    # Timestamp
    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
    ax.text(W - 0.4, brand_y, now_str, color=GRAY, fontsize=7,
            ha="right", va="center", fontfamily="monospace", alpha=0.5, zorder=3)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=100, bbox_inches="tight",
                facecolor=BG, edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return buf
