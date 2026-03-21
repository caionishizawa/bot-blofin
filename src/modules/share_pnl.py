"""
Share PNL — generates a shareable PNL card PNG for social sharing.
"""

import io
import logging
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

logger = logging.getLogger(__name__)

# Dark theme (consistent with chart_generator.py)
COLORS = {
    "bg":        "#0d1117",
    "panel":     "#161b22",
    "panel2":    "#1c2128",
    "text":      "#c9d1d9",
    "text_dim":  "#8b949e",
    "grid":      "#21262d",
    "green":     "#3fb950",
    "red":       "#f85149",
    "blue":      "#58a6ff",
    "orange":    "#d29922",
    "border":    "#30363d",
    "green_dim": "#3fb95040",
    "red_dim":   "#f8514940",
}


def create_share_card(stats: dict, recent_trades: list, watermark: str = "NPK Sinais") -> io.BytesIO:
    """Generate a shareable PNL card PNG.

    Args:
        stats: dict from PerformanceDB.get_stats()
        recent_trades: list of recent closed trades (up to 20)
        watermark: brand name

    Returns:
        BytesIO PNG buffer
    """
    total_pnl = stats.get("total_pnl", 0.0)
    win_rate = stats.get("win_rate", 0.0)
    total_trades = stats.get("total_trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    profit_factor = stats.get("profit_factor", 0.0)
    avg_win = stats.get("avg_win", 0.0)
    avg_loss = stats.get("avg_loss", 0.0)

    # Use up to 20 most recent trades for bar chart
    trades = recent_trades[:20]
    pnl_values = [t.get("pnl_pct", 0) for t in trades]

    fig = plt.figure(figsize=(10, 6), dpi=120, facecolor=COLORS["bg"])

    # Layout: top header + left stats + right bar chart
    gs = fig.add_gridspec(
        3, 2,
        height_ratios=[0.8, 2.5, 0.7],
        width_ratios=[1.1, 1],
        hspace=0.12,
        wspace=0.08,
        left=0.05, right=0.97,
        top=0.93, bottom=0.08,
    )

    # ─── Header bar ───────────────────────────────────────────────
    ax_header = fig.add_subplot(gs[0, :])
    ax_header.set_facecolor(COLORS["panel"])
    ax_header.set_xticks([])
    ax_header.set_yticks([])
    for spine in ax_header.spines.values():
        spine.set_color(COLORS["border"])
        spine.set_linewidth(0.5)

    pnl_color = COLORS["green"] if total_pnl >= 0 else COLORS["red"]
    pnl_str = f"+{total_pnl:.2f}%" if total_pnl >= 0 else f"{total_pnl:.2f}%"

    ax_header.text(0.03, 0.5, watermark,
                   transform=ax_header.transAxes,
                   color=COLORS["text"], fontsize=16, fontweight="bold",
                   va="center", ha="left")
    ax_header.text(0.5, 0.5, "Resultados de Trading",
                   transform=ax_header.transAxes,
                   color=COLORS["text_dim"], fontsize=10,
                   va="center", ha="center")
    ax_header.text(0.97, 0.5,
                   datetime.now(timezone.utc).strftime("%d/%m/%Y"),
                   transform=ax_header.transAxes,
                   color=COLORS["text_dim"], fontsize=9,
                   va="center", ha="right")

    # ─── Stats panel (left) ───────────────────────────────────────
    ax_stats = fig.add_subplot(gs[1, 0])
    ax_stats.set_facecolor(COLORS["panel"])
    ax_stats.set_xticks([])
    ax_stats.set_yticks([])
    for spine in ax_stats.spines.values():
        spine.set_color(COLORS["border"])
        spine.set_linewidth(0.5)

    # Big PNL number
    ax_stats.text(0.5, 0.82, pnl_str,
                  transform=ax_stats.transAxes,
                  color=pnl_color, fontsize=38, fontweight="bold",
                  va="top", ha="center")
    ax_stats.text(0.5, 0.62, "PNL Total (30 dias)",
                  transform=ax_stats.transAxes,
                  color=COLORS["text_dim"], fontsize=9,
                  va="top", ha="center")

    # Win rate bar
    wr_filled = round(win_rate / 10)
    wr_bar = "█" * wr_filled + "░" * (10 - wr_filled)
    ax_stats.text(0.08, 0.44, f"Win Rate  {wr_bar}  {win_rate:.1f}%",
                  transform=ax_stats.transAxes,
                  color=COLORS["blue"], fontsize=9, fontfamily="monospace",
                  va="top", ha="left")

    # Key metrics grid
    metrics = [
        (f"{total_trades}", "Trades"),
        (f"{wins}W / {losses}L", "Resultado"),
        (f"+{avg_win:.1f}% / {avg_loss:.1f}%", "Avg Win / Loss"),
        (f"{profit_factor:.2f}" if profit_factor < 999 else "999+", "Profit Factor"),
    ]
    for idx, (val, label) in enumerate(metrics):
        col = idx % 2
        row = idx // 2
        x_pos = 0.08 + col * 0.5
        y_pos = 0.30 - row * 0.17
        ax_stats.text(x_pos, y_pos, val,
                      transform=ax_stats.transAxes,
                      color=COLORS["text"], fontsize=11, fontweight="bold",
                      va="top", ha="left")
        ax_stats.text(x_pos, y_pos - 0.09, label,
                      transform=ax_stats.transAxes,
                      color=COLORS["text_dim"], fontsize=7.5,
                      va="top", ha="left")

    # ─── Bar chart (right) ────────────────────────────────────────
    ax_bars = fig.add_subplot(gs[1, 1])
    ax_bars.set_facecolor(COLORS["panel"])
    for spine in ax_bars.spines.values():
        spine.set_color(COLORS["border"])
        spine.set_linewidth(0.5)
    ax_bars.tick_params(colors=COLORS["text_dim"], labelsize=7)
    ax_bars.grid(axis="y", color=COLORS["grid"], alpha=0.5, linewidth=0.3)

    if pnl_values:
        x = np.arange(len(pnl_values))
        bar_colors = [COLORS["green"] if p >= 0 else COLORS["red"] for p in pnl_values]
        ax_bars.bar(x, pnl_values, color=bar_colors, width=0.75, alpha=0.85)
        ax_bars.axhline(0, color=COLORS["text_dim"], linewidth=0.5, alpha=0.5)
        ax_bars.set_xticks([])
        ax_bars.set_ylabel("PNL %", color=COLORS["text_dim"], fontsize=7.5)
    else:
        ax_bars.text(0.5, 0.5, "Sem trades ainda",
                     transform=ax_bars.transAxes,
                     color=COLORS["text_dim"], fontsize=9,
                     va="center", ha="center")

    ax_bars.text(0.03, 0.97, f"Últimos {len(pnl_values)} trades",
                 transform=ax_bars.transAxes,
                 color=COLORS["text_dim"], fontsize=7.5,
                 va="top", ha="left")

    # ─── Footer ──────────────────────────────────────────────────
    ax_footer = fig.add_subplot(gs[2, :])
    ax_footer.set_facecolor(COLORS["panel2"])
    ax_footer.set_xticks([])
    ax_footer.set_yticks([])
    for spine in ax_footer.spines.values():
        spine.set_color(COLORS["border"])
        spine.set_linewidth(0.3)

    ax_footer.text(0.03, 0.5,
                   "⚠️ Resultados passados não garantem lucros futuros. Trading envolve risco.",
                   transform=ax_footer.transAxes,
                   color=COLORS["text_dim"], fontsize=7,
                   va="center", ha="left", style="italic")
    ax_footer.text(0.97, 0.5, watermark,
                   transform=ax_footer.transAxes,
                   color=COLORS["text_dim"], fontsize=7.5,
                   va="center", ha="right", alpha=0.6)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", facecolor=COLORS["bg"], bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf
