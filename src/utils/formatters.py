"""
Telegram Message Formatters — aesthetic signal cards, trade updates, and reports.
"""

from datetime import datetime, timezone


def _bar(filled: int, total: int = 10, fill: str = "█", empty: str = "░") -> str:
    """Return a visual progress bar string."""
    filled = max(0, min(total, filled))
    return fill * filled + empty * (total - filled)


def _confidence_bar(confidence: int) -> str:
    filled = round(confidence / 10)
    return _bar(filled)


def _rr_label(rr: float) -> str:
    if rr >= 2.5:
        return "Excelente"
    if rr >= 2.0:
        return "Ótimo"
    if rr >= 1.5:
        return "Bom"
    return "Baixo"


def _escape_md(text: str) -> str:
    """Escape Telegram MarkdownV1 special characters."""
    for ch in ["_", "*", "`", "[", "]", "(", ")"]:
        text = text.replace(ch, f"\\{ch}")
    return text


def format_signal_message(signal: dict, analysis: str = "", ref_link: str = "") -> str:
    """Format a new signal message for Telegram — clean aesthetic card."""
    direction = signal["direction"]
    pair = signal.get("pair", "N/A")
    tf = signal.get("timeframe", "1H")
    entry = signal.get("entry") or 0
    sl = signal.get("stop_loss") or 0
    tp1 = signal.get("tp1") or 0
    tp2 = signal.get("tp2") or 0
    tp3 = signal.get("tp3") or 0
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio") or 0
    score = signal.get("score", 0)

    if direction == "LONG":
        dir_emoji = "🟢"
        dir_label = "LONG  ↑"
    else:
        dir_emoji = "🔴"
        dir_label = "SHORT  ↓"

    risk_pct = abs(entry - sl) / entry * 100 if entry else 0
    potential_pct = abs(tp3 - entry) / entry * 100 if entry else 0

    conf_bar = _confidence_bar(confidence)
    rr_label = _rr_label(rr)

    now = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")

    lines = [
        f"{dir_emoji} *{dir_label}* — `{pair}` ({tf})",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📍 *Entrada:*  `{entry:,.2f}`",
        f"🛑 *Stop Loss:* `{sl:,.2f}`  _(-{risk_pct:.1f}%)_",
        f"",
        f"🎯 *TP1:* `{tp1:,.2f}`",
        f"🎯 *TP2:* `{tp2:,.2f}`",
        f"🏆 *TP3:* `{tp3:,.2f}`  _(+{potential_pct:.1f}%)_",
        f"",
        f"📊 *Confiança:* {conf_bar} {confidence}%",
        f"⚖️ *R:R:* `{rr}:1`  —  {rr_label}",
        f"⭐ *Score:* {score:.0f}/6  •  _{now}_",
    ]

    if analysis:
        safe_analysis = _escape_md(analysis)
        lines.append(f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        lines.append(f"🤖 *Análise IA:*")
        lines.append(safe_analysis)

    if ref_link:
        lines.append(f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        lines.append(f"🔗 [Opere na BloFin com alavancagem]({ref_link})")

    return "\n".join(lines)


def format_update_message(pair: str, event: str, trade: dict) -> str:
    """Format a trade update (TP/SL hit) message — aesthetic result card."""
    event_configs = {
        "TP1_HIT": ("🎯",    "TP1 ATINGIDO",             True),
        "TP2_HIT": ("🎯🎯", "TP2 ATINGIDO",              True),
        "TP3_HIT": ("🏆",    "TP3 ATINGIDO — FULL TARGET", True),
        "SL_HIT":  ("🛑",    "STOP ATIVADO",              False),
    }
    emoji, label, is_win = event_configs.get(event, ("📢", event.replace("_", " "), True))

    entry = trade.get("entry") or 0
    exit_price = trade.get("exit_price") or trade.get("current_price") or 0
    pnl = trade.get("pnl_pct") or 0
    direction = trade.get("direction", "LONG")
    opened_at = trade.get("opened_at", "")
    rr = trade.get("rr_ratio")
    duration_seconds = trade.get("duration_seconds")

    pnl_emoji = "✅" if pnl >= 0 else "❌"
    pnl_str = f"+{pnl:.2f}%" if pnl >= 0 else f"{pnl:.2f}%"

    lines = [
        f"{emoji} *{label}*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📌 *Par:* `{pair}`  •  {direction}",
        f"📍 *Entrada:* `{entry:,.2f}`",
        f"💰 *Saída:* `{exit_price:,.2f}`",
        f"",
        f"{pnl_emoji} *PNL: `{pnl_str}`*",
    ]

    if rr is not None and rr > 0:
        lines.append(f"⚖️ *R:R realizado:* `{rr}:1`")

    # Duration from stored seconds (precise) or from timestamps
    if duration_seconds is not None:
        hours = int(duration_seconds // 3600)
        mins = int((duration_seconds % 3600) // 60)
        duration = f"{hours}h {mins}m" if hours else f"{mins}m"
        lines.append(f"⏱ *Duração:* {duration}")
    elif opened_at:
        try:
            opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - opened
            hours = int(delta.total_seconds() // 3600)
            mins = int((delta.total_seconds() % 3600) // 60)
            duration = f"{hours}h {mins}m" if hours else f"{mins}m"
            lines.append(f"⏱ *Duração:* {duration}")
        except Exception:
            pass

    return "\n".join(lines)


def format_stats_message(stats: dict) -> str:
    """Format performance stats for Telegram — clean report card."""
    total = stats.get("total_trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    wr = stats.get("win_rate", 0.0)
    total_pnl = stats.get("total_pnl", 0.0)
    max_dd = stats.get("max_drawdown", 0.0)
    pf = stats.get("profit_factor", 0.0)
    avg_win = stats.get("avg_win", 0.0)
    avg_loss = stats.get("avg_loss", 0.0)
    avg_dur = stats.get("avg_duration_hours", 0.0)

    wr_bar = _bar(round(wr / 10))
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_str = f"+{total_pnl:.2f}%" if total_pnl >= 0 else f"{total_pnl:.2f}%"
    pf_str = "999+" if pf >= 999 else f"{pf:.2f}"

    lines = [
        f"📊 *Performance — Últimos 30 dias*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📋 *Trades:* {total}  •  ✅ {wins} wins  •  ❌ {losses} losses",
        f"",
        f"🎯 *Win Rate:* {wr_bar} {wr:.1f}%",
        f"{pnl_emoji} *PNL Total:* `{pnl_str}`",
        f"",
        f"📐 *Profit Factor:* `{pf_str}`",
        f"📉 *Max Drawdown:* `{max_dd:.1f}%`",
        f"",
        f"💚 *Avg Win:* `+{avg_win:.2f}%`  •  💔 *Avg Loss:* `{avg_loss:.2f}%`",
        f"⏱ *Duração média:* {avg_dur:.1f}h",
    ]

    return "\n".join(lines)


def format_trades_list(trades: list) -> str:
    """Format active trades list."""
    if not trades:
        return "📭 *Nenhum trade ativo no momento.*"

    lines = [f"📋 *Trades Ativos* ({len(trades)})", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
    for t in trades:
        emoji = "🟢" if t["direction"] == "LONG" else "🔴"
        pnl = t.get("pnl_pct") or 0
        pnl_str = f"+{pnl:.1f}%" if pnl >= 0 else f"{pnl:.1f}%"
        pnl_icon = "✅" if pnl >= 0 else "❌"
        entry = t.get("entry") or 0
        current = t.get("current_price") or entry
        lines.append(
            f"{emoji} `{t['pair']}` — {t['direction']}  {pnl_icon} `{pnl_str}`\n"
            f"   _Entrada: {entry:,.2f}  •  Atual: {current:,.2f}_"
        )

    return "\n".join(lines)
