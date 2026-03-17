"""
Telegram Message Formatters — templates for signal, update, and report messages.
"""


def format_signal_message(signal: dict, analysis: str = "", ref_link: str = "") -> str:
    """Format a new signal message for Telegram."""
    direction_emoji = "🟢" if signal["direction"] == "LONG" else "🔴"
    pair = signal.get("pair", "N/A")
    tf = signal.get("timeframe", "1H")

    lines = [
        f"{direction_emoji} *{signal['direction']}* — {pair} ({tf})",
        f"",
        f"📍 Entry: `{signal['entry']:.2f}`",
        f"🛑 Stop Loss: `{signal['stop_loss']:.2f}`",
        f"🎯 TP1: `{signal['tp1']:.2f}`",
        f"🎯 TP2: `{signal['tp2']:.2f}`",
        f"🎯 TP3: `{signal['tp3']:.2f}`",
        f"",
        f"📊 Confiança: {signal.get('confidence', 0)}% | R:R {signal.get('rr_ratio', 0)}:1",
        f"⭐ Score: {signal.get('score', 0):.0f}/6",
    ]

    if analysis:
        lines.append(f"\n💡 _{analysis}_")

    if ref_link:
        lines.append(f"\n🔗 [Opere na BloFin]({ref_link})")

    return "\n".join(lines)


def format_update_message(pair: str, event: str, trade: dict) -> str:
    """Format a trade update (TP/SL hit) message."""
    event_emojis = {
        "TP1_HIT": "🎯",
        "TP2_HIT": "🎯🎯",
        "TP3_HIT": "🎯🎯🎯",
        "SL_HIT": "🛑",
    }
    emoji = event_emojis.get(event, "📢")
    pnl = trade.get("pnl_pct", 0)
    pnl_emoji = "✅" if pnl > 0 else "❌"

    lines = [
        f"{emoji} *{event.replace('_', ' ')}* — {pair}",
        f"",
        f"📍 Entry: `{trade.get('entry', 0):.2f}`",
        f"💰 PNL: {pnl_emoji} `{pnl:+.2f}%`",
    ]

    return "\n".join(lines)


def format_stats_message(stats: dict) -> str:
    """Format performance stats for Telegram."""
    lines = [
        f"📈 *Performance Report*",
        f"",
        f"📊 Trades: {stats.get('total_trades', 0)}",
        f"✅ Wins: {stats.get('wins', 0)} | ❌ Losses: {stats.get('losses', 0)}",
        f"🎯 Win Rate: {stats.get('win_rate', 0):.1f}%",
        f"💰 Total PNL: `{stats.get('total_pnl', 0):+.2f}%`",
        f"📉 Max Drawdown: `{stats.get('max_drawdown', 0):.1f}%`",
        f"⚖️ Profit Factor: `{stats.get('profit_factor', 0):.2f}`",
    ]

    return "\n".join(lines)


def format_trades_list(trades: list) -> str:
    """Format active trades list."""
    if not trades:
        return "📭 Nenhum trade ativo no momento."

    lines = ["📋 *Trades Ativos*", ""]
    for t in trades:
        emoji = "🟢" if t["direction"] == "LONG" else "🔴"
        pnl = t.get("pnl_pct", 0)
        pnl_str = f"{'✅' if pnl > 0 else '❌'} {pnl:+.2f}%"
        lines.append(f"{emoji} {t['pair']} — {t['direction']} | {pnl_str} | {t['status']}")

    return "\n".join(lines)
