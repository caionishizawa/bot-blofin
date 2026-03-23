"""
Telegram Message Formatters — aesthetic signal cards, trade updates, and reports.
"""

from datetime import datetime, timezone

# BloFin taker fee per side (round-trip = 2x)
BLOFIN_TAKER_FEE = 0.0006  # 0.06%

# Partial close % at each TP level — must sum to 100
TP_SIZING = {"tp1": 50, "tp2": 30, "tp3": 20}


def _fmt_price(price: float) -> str:
    """Format price with enough decimals based on magnitude."""
    if price == 0:
        return "0"
    if price >= 1000:
        return f"{price:,.2f}"
    if price >= 100:
        return f"{price:,.3f}"
    if price >= 10:
        return f"{price:,.4f}"
    if price >= 1:
        return f"{price:,.5f}"
    if price >= 0.1:
        return f"{price:,.6f}"
    return f"{price:,.8f}"


def _bar(filled: int, total: int = 10, fill: str = "█", empty: str = "░") -> str:
    """Return a visual progress bar string."""
    filled = max(0, min(total, filled))
    return fill * filled + empty * (total - filled)


def _confidence_bar(confidence: int) -> str:
    filled = round(confidence / 10)
    return _bar(filled)


def _stars(score: float) -> str:
    """Return star emojis for a 0-10 score. Full stars up to int(score), dim remainder."""
    full = int(round(score))
    full = max(0, min(10, full))
    return "⭐" * full + "✦" * (10 - full)


def _rr_label(rr: float) -> str:
    if rr >= 2.5:
        return "Excelente"
    if rr >= 2.0:
        return "Ótimo"
    if rr >= 1.5:
        return "Bom"
    return "Baixo"


def calculate_leverage(rr: float, timeframe: str,
                       entry: float = 0, sl: float = 0,
                       bankroll: float = 1000.0, risk_pct: float = 2.0) -> int:
    """Alavancagem real baseada no risco fixo da banca.

    Fórmula:
      risco_usd   = bankroll × risk_pct%          → ex: $20
      sl_dist_pct = |entry − sl| / entry          → ex: 0.067%
      posição     = risco_usd / sl_dist_pct        → ex: $29,850
      alavancagem = posição / bankroll             → ex: 29.85 → 30x

    Caps: mínimo 2x, máximo 50x.
    """
    if entry and sl and abs(entry - sl) > 0:
        sl_dist = abs(entry - sl) / entry
        risk_usd = bankroll * risk_pct / 100
        position = risk_usd / sl_dist
        lev = position / bankroll
        return max(2, min(50, round(lev)))

    # Fallback por RR/timeframe se não tiver preços
    scalp_tf = {"1m", "3m", "5m", "15m", "30m"}
    if timeframe in scalp_tf:
        return 20
    if rr >= 3.0:   return 5
    if rr >= 2.5:   return 7
    if rr >= 2.0:   return 10
    if rr >= 1.5:   return 15
    return 20


def _net_return(entry: float, target: float, direction: str, leverage: int) -> float:
    """Return on capital (%) after fees for a given TP level."""
    if not entry:
        return 0.0
    if direction == "LONG":
        price_move_pct = (target - entry) / entry
    else:
        price_move_pct = (entry - target) / entry
    gross = price_move_pct * leverage * 100
    fee_cost = BLOFIN_TAKER_FEE * 2 * leverage * 100  # round-trip taker
    return gross - fee_cost


def format_signal_message(signal: dict, analysis: str = "", ref_link: str = "", mode: str = "scalp") -> str:
    """Format a new signal message for Telegram — clean aesthetic card."""
    direction = signal["direction"]
    pair = signal.get("pair", "N/A")
    tf = signal.get("timeframe", "1H")
    entry = signal.get("entry", 0)
    sl = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    tp2 = signal.get("tp2", 0)
    tp3 = signal.get("tp3", 0)
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio", 0)
    score = signal.get("score", 0)

    if direction == "LONG":
        dir_emoji = "🟢"
        dir_label = "LONG  ↑"
    else:
        dir_emoji = "🔴"
        dir_label = "SHORT  ↓"

    bankroll    = signal.get("bankroll", 1000.0)
    config_risk = signal.get("risk_pct", 2.0)
    sl_dist_pct = abs(entry - sl) / entry * 100 if entry else 0
    risk_usd    = bankroll * config_risk / 100

    conf_bar = _confidence_bar(confidence)

    # R:R ponderado real: considera fechamento parcial 50/30/20 em cada TP
    sl_dist_abs_rr = abs(entry - sl)
    if sl_dist_abs_rr > 0 and tp1 and tp2 and tp3:
        rr_tp1 = abs(tp1 - entry) / sl_dist_abs_rr
        rr_tp2 = abs(tp2 - entry) / sl_dist_abs_rr
        rr_tp3 = abs(tp3 - entry) / sl_dist_abs_rr
        rr = round(rr_tp1 * 0.50 + rr_tp2 * 0.30 + rr_tp3 * 0.20, 2)

    rr_label = _rr_label(rr)

    lev = signal.get("swing_override_lev") or calculate_leverage(
        rr, tf, entry=entry, sl=sl, bankroll=bankroll, risk_pct=config_risk
    )
    fee_cost_pct = BLOFIN_TAKER_FEE * 2 * lev * 100

    # PNL em USD por nível (risco fixo × RR do nível × % da posição fechada)
    sl_dist_abs = abs(entry - sl)
    def pnl_usd_at(tp_price, close_pct):
        if not sl_dist_abs: return 0.0
        rr_level = abs(tp_price - entry) / sl_dist_abs
        return round(risk_usd * rr_level * (close_pct / 100), 2)

    usd1    = pnl_usd_at(tp1, TP_SIZING["tp1"])
    usd2    = pnl_usd_at(tp2, TP_SIZING["tp2"])
    usd3    = pnl_usd_at(tp3, TP_SIZING["tp3"])
    usd_sl  = -risk_usd
    total   = round(usd1 + usd2 + usd3, 2)

    pct1   = round(usd1  / bankroll * 100, 2) if bankroll else 0
    pct2   = round(usd2  / bankroll * 100, 2) if bankroll else 0
    pct3   = round(usd3  / bankroll * 100, 2) if bankroll else 0
    pct_sl = round(usd_sl / bankroll * 100, 2) if bankroll else 0

    now = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")
    mode_badge = "  _— swing_" if mode == "swing" else ""

    lines = [
        f"{dir_emoji} *{dir_label}* — `{pair}` ({tf}){mode_badge}",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📍 *Entrada:*  `{_fmt_price(entry)}`",
        f"╷",
        f"├ *SL* `{_fmt_price(sl)}`  _({pct_sl:.2f}% banca  •  ${abs(usd_sl):.2f} risco)_",
        f"├ *TP1* `{_fmt_price(tp1)}`  _(+{pct1:.2f}% banca  •  +${usd1:.2f}  •  fechar {TP_SIZING['tp1']}%)_",
        f"├ *TP2* `{_fmt_price(tp2)}`  _(+{pct2:.2f}% banca  •  +${usd2:.2f}  •  fechar {TP_SIZING['tp2']}%)_",
        f"└ *TP3* `{_fmt_price(tp3)}`  _(+{pct3:.2f}% banca  •  +${usd3:.2f}  •  fechar {TP_SIZING['tp3']}%)_",
        f"",
        f"💰 _Se todos os TPs baterem: *+${total:.2f}* (+{round(total/bankroll*100,2)}% da banca)_",
        f"⚡ *Alavancagem:* `{lev}x`  •  💸 _Fee ~{fee_cost_pct:.1f}% já descontada_",
        f"",
        f"📊 *Confiança:* {conf_bar} {confidence}%",
        f"⚖️ *R:R:* `{rr}:1`  —  {rr_label}",
        f"🏅 *Avaliação:* {_stars(score)}  `{score:.1f}/10`  •  _{now}_",
    ]

    if analysis:
        safe_analysis = analysis.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
        lines.append(f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        lines.append(f"📈 *Análise Gráfica Quantitativa & Qualitativa:*")
        lines.append(safe_analysis)

    if ref_link:
        lines.append(f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄")
        lines.append(f"🔗 [Opere na BloFin com alavancagem]({ref_link})")

    return "\n".join(lines)


def format_update_message(pair: str, event: str, trade: dict, bankroll: float = 1000.0) -> str:
    """Format a trade update (TP/SL hit) message com PNL parcial e status do trade."""
    # Qual % da posição foi fechada em cada TP
    _close_pct  = {"TP1_HIT": 50, "TP2_HIT": 30, "TP3_HIT": 20, "SL_HIT": 100}
    # Quanto ainda resta aberto após o evento
    _remaining  = {"TP1_HIT": 50, "TP2_HIT": 20, "TP3_HIT": 0,  "SL_HIT": 0}

    event_configs = {
        "TP1_HIT": ("🎯", "TP1 ATINGIDO — 50% fechado"),
        "TP2_HIT": ("🎯🎯", "TP2 ATINGIDO — 80% fechado"),
        "TP3_HIT": ("🏆", "TP3 ATINGIDO — POSIÇÃO ENCERRADA"),
        "SL_HIT":  ("🛑", "STOP ATIVADO — POSIÇÃO ENCERRADA"),
    }
    emoji, label = event_configs.get(event, ("📢", event.replace("_", " ")))

    entry      = trade.get("entry", 0)
    exit_price = trade.get("exit_price", trade.get("current_price", 0))
    pnl        = trade.get("pnl_pct", 0)
    direction  = trade.get("direction", "LONG")
    opened_at  = trade.get("opened_at", "")
    rr         = trade.get("rr_ratio", 0)
    remaining  = _remaining.get(event, 0)
    closed_now = _close_pct.get(event, 100)

    # PNL acumulado até este evento (inclui todos os TPs já batidos)
    from modules.performance import PerformanceDB
    pnl_usd       = PerformanceDB.calc_pnl_usd(trade, bankroll)
    pnl_banca_pct = (pnl_usd / bankroll * 100) if bankroll else 0.0

    pnl_emoji = "✅" if pnl_usd >= 0 else "❌"
    usd_str   = f"+${pnl_usd:.2f}"       if pnl_usd >= 0       else f"-${abs(pnl_usd):.2f}"
    pct_str   = f"+{pnl_banca_pct:.2f}%" if pnl_banca_pct >= 0 else f"{pnl_banca_pct:.2f}%"
    move_str  = f"+{pnl:.3f}%"           if pnl >= 0           else f"{pnl:.3f}%"

    lines = [
        f"{emoji} *{label}*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📌 *Par:* `{pair}`  •  {direction}",
        f"📍 *Entrada:* `{_fmt_price(entry)}`",
        f"💰 *Parcial:* `{_fmt_price(exit_price)}`  _({closed_now}% da posição)_",
        f"",
        f"{pnl_emoji} *PNL acumulado: `{usd_str} USDT`*  •  `{pct_str} da banca`",
        f"_Movimento: {move_str}_",
    ]

    if rr:
        lines.append(f"⚖️ *R:R:* `{rr}:1`")

    # Status: trade ainda aberto ou encerrado
    if remaining > 0:
        lines.append(f"")
        lines.append(f"📊 *{remaining}% da posição ainda aberta* — aguardando próximo alvo")
    else:
        lines.append(f"")
        lines.append(f"🔒 *Posição encerrada*")

    if opened_at:
        try:
            opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            delta = now - opened
            hours = int(delta.total_seconds() // 3600)
            mins  = int((delta.total_seconds() % 3600) // 60)
            duration = f"{hours}h {mins}m" if hours else f"{mins}m"
            lines.append(f"⏱ *Duração:* {duration}")
        except Exception:
            pass

    return "\n".join(lines)


def _stats_block(label: str, stats: dict, starting_bankroll: float = 1000.0) -> list:
    """Single period stats block lines."""
    total = stats.get("total_trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    wr = stats.get("win_rate", 0.0)
    total_pnl_usd = stats.get("total_pnl_usd", 0.0)
    current_bankroll = stats.get("current_bankroll", starting_bankroll)
    max_dd = stats.get("max_drawdown", 0.0)
    max_dd_usd = stats.get("max_drawdown_usd", 0.0)
    pf = stats.get("profit_factor", 0.0)
    avg_win_usd = stats.get("avg_win_usd", 0.0)
    avg_loss_usd = stats.get("avg_loss_usd", 0.0)

    if total == 0:
        return [f"*{label}* — _sem dados_", ""]

    wr_bar = _bar(round(wr / 10))
    pnl_emoji = "📈" if total_pnl_usd >= 0 else "📉"
    pnl_usd_str = f"+${total_pnl_usd:.2f}" if total_pnl_usd >= 0 else f"-${abs(total_pnl_usd):.2f}"
    pf_str = f"{pf:.2f}" if pf != float("inf") else "∞"
    banca_str = f"${current_bankroll:.2f}"

    return [
        f"*{label}*",
        f"  📋 {total} trades  •  ✅ {wins}W  ❌ {losses}L",
        f"  🎯 Win Rate: {wr_bar} {wr:.1f}%",
        f"  {pnl_emoji} PNL: `{pnl_usd_str}`  •  📐 PF: `{pf_str}`",
        f"  💼 Banca atual: `{banca_str}`  •  📉 Max DD: `${max_dd_usd:.2f}` ({max_dd:.1f}%)",
        f"  💚 Avg Win: `+${avg_win_usd:.2f}`  •  💔 Avg Loss: `${avg_loss_usd:.2f}`",
        "",
    ]


def format_stats_message(stats: dict, starting_bankroll: float = 1000.0) -> str:
    """Format performance stats — supports single period (dict) or multi-period (nested dict)."""
    # Multi-period format: {"weekly": {...}, "monthly": {...}, "annual": {...}}
    if "weekly" in stats or "monthly" in stats or "annual" in stats:
        now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")
        lines = [
            f"📊 *Relatório de Performance*",
            f"_Banca inicial: ${starting_bankroll:.0f} USDT  •  Atualizado: {now}_",
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            "",
        ]
        period_map = [
            ("📅 Semanal (7d)", "weekly"),
            ("📆 Mensal (30d)", "monthly"),
            ("🗓 Anual (365d)", "annual"),
        ]
        for label, key in period_map:
            if key in stats:
                lines += _stats_block(label, stats[key], starting_bankroll)
        return "\n".join(lines)

    # Single period (legacy)
    total = stats.get("total_trades", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)
    wr = stats.get("win_rate", 0.0)
    total_pnl = stats.get("total_pnl", 0.0)
    max_dd = stats.get("max_drawdown", 0.0)
    pf = stats.get("profit_factor", 0.0)
    avg_win = stats.get("avg_win", 0.0)
    avg_loss = stats.get("avg_loss", 0.0)

    wr_bar = _bar(round(wr / 10))
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_str = f"+{total_pnl:.2f}%" if total_pnl >= 0 else f"{total_pnl:.2f}%"

    lines = [
        f"📊 *Performance — Últimos 30 dias*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📋 *Trades:* {total}  •  ✅ {wins} wins  •  ❌ {losses} losses",
        f"",
        f"🎯 *Win Rate:* {wr_bar} {wr:.1f}%",
        f"{pnl_emoji} *PNL Total:* `{pnl_str}`",
        f"",
        f"📐 *Profit Factor:* `{pf:.2f}`",
        f"📉 *Max Drawdown:* `{max_dd:.1f}%`",
        f"",
        f"💚 *Avg Win:* `+{avg_win:.2f}%`  •  💔 *Avg Loss:* `{avg_loss:.2f}%`",
    ]
    return "\n".join(lines)


def format_trades_list(trades: list, current_bankroll: float = 0.0,
                       realized_pnl: float = 0.0, unrealized_pnl: float = 0.0,
                       starting_bankroll: float = 1000.0) -> str:
    """Format active trades list com PNL não realizado por trade e banca atual."""
    if not trades:
        return "📭 *Nenhum trade ativo no momento.*"

    lines = [f"📋 *Trades Ativos* ({len(trades)})", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]

    for t in trades:
        from modules.performance import PerformanceDB
        emoji   = "🟢" if t["direction"] == "LONG" else "🔴"
        entry   = t.get("entry", 0)
        current = t.get("current_price", entry)

        # PNL não realizado do restante aberto
        unreal  = t.get("unrealized_usd", 0.0)
        unreal_pct = (unreal / starting_bankroll * 100) if starting_bankroll else 0.0
        u_str   = f"+${unreal:.2f}" if unreal >= 0 else f"-${abs(unreal):.2f}"
        up_str  = f"+{unreal_pct:.2f}%" if unreal_pct >= 0 else f"{unreal_pct:.2f}%"
        u_icon  = "📈" if unreal >= 0 else "📉"

        # TPs já batidos
        tp_status = ""
        if t.get("tp1_hit"): tp_status += "TP1✅ "
        if t.get("tp2_hit"): tp_status += "TP2✅ "

        lines.append(
            f"{emoji} *`{t['pair']}`* — {t['direction']}  {tp_status}\n"
            f"   📍 Entrada: `{_fmt_price(entry)}`  •  Atual: `{_fmt_price(current)}`\n"
            f"   {u_icon} Não realizado: `{u_str}` ({up_str} da banca)"
        )

    # Resumo da banca
    if current_bankroll:
        banca_change = current_bankroll - starting_bankroll
        b_emoji = "📈" if banca_change >= 0 else "📉"
        b_str   = f"+${banca_change:.2f}" if banca_change >= 0 else f"-${abs(banca_change):.2f}"
        lines += [
            "",
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            f"💼 *Banca atual: `${current_bankroll:.2f}`*  {b_emoji} `{b_str}`",
            f"_Realizado: ${realized_pnl:+.2f}  •  Não realizado: ${unrealized_pnl:+.2f}_",
        ]

    return "\n".join(lines)
