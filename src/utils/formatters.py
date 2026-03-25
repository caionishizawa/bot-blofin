"""
Telegram Message Formatters — sideradogcripto.
Sinais completos para todos. FREE e VIP recebem o mesmo sinal.
Diferenciação: /ask (VIP ilimitado), timing e portfolio diário.
"""

import random
from datetime import datetime, timezone

# ─── Branding ──────────────────────────────────────────────────────────────
BRAND_NAME    = "sideradogcripto"
BRAND_TAG     = "@sideradogcripto"
BRAND_EMOJI   = "⚡"
BRAND_HEADER  = f"{BRAND_EMOJI} *{BRAND_NAME}*"

# ─── Setup labels por tipo ──────────────────────────────────────────────────
# (emoji + label, subtítulo descritivo)
SETUP_META = {
    "scalp":    ("⚡ SCALP",      "Entrada rápida. Stop curto, alvo definido."),
    "swing":    ("📈 SWING",      "Setup de médio prazo. Deixa o trade respirar."),
    "sniper":   ("🎯 SNIPER",     "Stop cirúrgico. RR excepcional. Não aparece todo dia."),
    "reversal": ("🔄 REVERSÃO",   "Divergência ativa. Possível mudança de direção."),
    "breakout": ("💥 BREAKOUT",   "Rompimento de estrutura. Momentum a favor."),
    "retest":   ("🔁 RETEST",     "Retorno para zona rompida. Entrada de tendência."),
    "premium":  ("💎 PREMIUM",    "Confluência múltipla. Setup de alta qualidade."),
}

# BloFin fee
BLOFIN_TAKER_FEE = 0.0006
TP_SIZING = {"tp1": 20, "tp2": 50, "tp3": 30}
# TP1 = 20%: parcial rápido + mover SL para breakeven
# TP2 = 50%: realização principal
# TP3 = 30%: runner — deixa o trade trabalhar

# ─── Personalidades ────────────────────────────────────────────────────────
# 5 vozes que rotacionam. Cada uma tem frases de abertura por contexto.
# Contextos: "bullish", "bearish", "sniper", "swing", "neutro"

PERSONALITIES = {

    "analista": {
        "bullish": [
            "Setup confirmado. Confluência técnica sobre zona de demanda institucional.",
            "Estrutura de mercado favorável. Entrada alinhada com fluxo de ordem comprador.",
            "OB de alta intocado. Preço retornou para a zona — momento de posicionamento.",
            "Divergência bullish confirmada no RSI. Bias comprador ativo.",
        ],
        "bearish": [
            "Zona de oferta institucional identificada. Pressão vendedora predominante.",
            "Estrutura rompida para baixo. Retest concluído — entrada vendedora válida.",
            "OB bearish preservado. Confluência com resistência de topo anterior.",
            "RSI sobrecomprado com divergência de baixa. Setup de reversão técnico.",
        ],
        "sniper": [
            "Stop cirúrgico. Risco mínimo, alvo estendido. Essa entrada exige precisão.",
            "Setup sniper identificado. Mecha de liquidez coletada — entrada de alta qualidade.",
            "Relação risco/retorno fora do padrão. Esse tipo de setup não aparece todo dia.",
        ],
        "swing": [
            "Leitura de 4H concluída. Tendência macro favorável ao posicionamento.",
            "Swing setup ativo. Paciência recompensada com alvos estendidos.",
        ],
    },

    "trader": {
        "bullish": [
            "Esse setup eu reconheço. Comprador posicionado antes do movimento.",
            "Mercado deu a zona. Agora é entrar com disciplina e deixar o trade trabalhar.",
            "Não complica. Zona de demanda, stop abaixo, alvo acima. Vai na execução.",
            "Esse é o tipo de entrada que eu aguardo. Limpa, estruturada, sem ruído.",
        ],
        "bearish": [
            "Zona de oferta clara. Mercado não mente quando o setup é assim.",
            "Vendedor institucional presente. A estrutura fala por si só.",
            "Short limpo. Stop acima do OB, alvos abaixo. Risco calculado.",
        ],
        "sniper": [
            "Stop apertado, alvo longo. Ou acerta ou corta rápido. Sem meio-termo.",
            "Esse é um dos setups que mais gosto. Assimetria real de risco/retorno.",
            "RR de dois dígitos não aparece todo ciclo. Quando aparece, a posição é pequena e o alvo fala alto.",
        ],
        "swing": [
            "Swing no 4H. Deixa o trade respirar, não fica olhando tick a tick.",
            "Esse tipo de trade fica aberto dias. Exige paciência, não ansiedade.",
        ],
    },

    "mentor": {
        "bullish": [
            "Repara no que aconteceu aqui: preço voltou para onde os compradores estavam ativos. Isso é zona de demanda.",
            "Antes de entrar, entenda o porquê: RSI divergiu, OB preservado, tendência favorável. Três sinais, uma entrada.",
            "O mercado sempre sinaliza antes de se mover. Aprender a ler esses sinais é o que separa amador de profissional.",
        ],
        "bearish": [
            "Observe a estrutura: máximos decrescentes, zona de oferta respeitada. O mercado está nos dizendo algo.",
            "Cada componente do setup tem uma razão de existir. OB bearish + RSI sobrecomprado = desequilíbrio vendedor.",
        ],
        "sniper": [
            "Setup sniper: stop cirúrgico em zona de liquidez, alvo no próximo desequilíbrio. Assimetria máxima.",
            "Nem todo trade precisa de stop largo. Às vezes o mercado entrega precisão — e quando entrega, o RR é generoso.",
        ],
        "swing": [
            "No swing, o timeframe maior filtra o ruído. O que parece caótico no 1H, no 4H é uma tendência clara.",
        ],
    },

    "estrategista": {
        "bullish": [
            "O mercado está nos dando uma janela. Demanda institucional ativa, estrutura limpa, momento favorável.",
            "Contexto macro e técnico alinhados. Quando o mercado converge assim, a probabilidade pesa a nosso favor.",
            "Posicionamento antes do movimento. Quem entende o fluxo entra antes, não depois.",
        ],
        "bearish": [
            "Oferta no topo, demanda esgotada. O desequilíbrio favorece o lado vendedor nesse nível.",
            "Estrutura de distribuição identificada. O movimento descendente é o caminho de menor resistência.",
        ],
        "sniper": [
            "Entrada cirúrgica em zona de alta probabilidade. Risco minimizado, recompensa amplificada.",
            "Esse tipo de assimetria — arriscar pouco para ganhar muito — é o fundamento de uma gestão profissional.",
        ],
        "swing": [
            "Tendência de médio prazo favorável. Esse trade é sobre alinhar com o fluxo, não contra ele.",
        ],
    },

    "neutro": {
        "bullish": [
            "Setup de compra identificado.",
            "Zona de entrada ativa.",
            "Sinal de alta confirmado.",
        ],
        "bearish": [
            "Setup de venda identificado.",
            "Zona de entrada ativa.",
            "Sinal de baixa confirmado.",
        ],
        "sniper": [
            "Setup sniper ativo.",
            "Entrada de alta assimetria.",
        ],
        "swing": [
            "Swing setup identificado.",
        ],
    },
}

# Frases de contexto pós-performance (nunca menciona trade negativo)
CONTEXT_PHRASES = {
    "streak_win": [
        f"_{BRAND_TAG} — consistência é o resultado de método, não sorte._",
        f"_{BRAND_TAG} — cada acerto é consequência do processo._",
        f"_{BRAND_TAG} — disciplina no risco, paciência no alvo._",
    ],
    "neutral": [
        f"_{BRAND_TAG} — o mercado oferece oportunidade para quem sabe esperar._",
        f"_{BRAND_TAG} — gestão de risco antes de qualquer trade._",
        f"_{BRAND_TAG} — método, não emoção._",
    ],
    "recovering": [
        f"_{BRAND_TAG} — o próximo setup é o que importa._",
        f"_{BRAND_TAG} — consistência se constrói trade a trade._",
    ],
}


# ─── Helpers ───────────────────────────────────────────────────────────────

def _fmt_price(price: float) -> str:
    if price == 0: return "0"
    if price >= 1000:  return f"{price:,.2f}"
    if price >= 100:   return f"{price:,.3f}"
    if price >= 10:    return f"{price:,.4f}"
    if price >= 1:     return f"{price:,.5f}"
    if price >= 0.1:   return f"{price:,.6f}"
    return f"{price:,.8f}"


def _bar(filled: int, total: int = 10, fill: str = "█", empty: str = "░") -> str:
    filled = max(0, min(total, filled))
    return fill * filled + empty * (total - filled)


def _confidence_bar(confidence: int) -> str:
    return _bar(round(confidence / 10))


def _rr_label(rr: float) -> str:
    if rr >= 5.0: return "Excepcional 🔥"
    if rr >= 3.0: return "Excelente"
    if rr >= 2.0: return "Ótimo"
    if rr >= 1.5: return "Bom"
    return "Moderado"


def _pick_personality(mode: str = "scalp") -> tuple[str, str]:
    """Returns (personality_name, context_key)."""
    names = list(PERSONALITIES.keys())
    # Sniper e swing têm bias de personalidade
    if mode == "sniper":
        name = random.choice(["analista", "trader", "estrategista"])
        ctx  = "sniper"
    elif mode == "swing":
        name = random.choice(["analista", "mentor", "estrategista"])
        ctx  = "swing"
    else:
        name = random.choice(names)
        ctx  = None  # definido por direction
    return name, ctx


def _opening_phrase(direction: str, mode: str, recent_wins: int = 0) -> str:
    name, ctx = _pick_personality(mode)
    if ctx is None:
        ctx = "bullish" if direction == "LONG" else "bearish"
    phrases = PERSONALITIES[name].get(ctx, PERSONALITIES["neutro"].get(ctx, ["Setup identificado."]))
    return random.choice(phrases)


def _context_footer(recent_wins: int, recent_losses: int) -> str:
    if recent_wins >= 3 and recent_losses == 0:
        return random.choice(CONTEXT_PHRASES["streak_win"])
    if recent_losses > recent_wins:
        return random.choice(CONTEXT_PHRASES["recovering"])
    return random.choice(CONTEXT_PHRASES["neutral"])


def calculate_leverage(rr: float, timeframe: str,
                       entry: float = 0, sl: float = 0,
                       bankroll: float = 1000.0, risk_pct: float = 2.0) -> int:
    if entry and sl and abs(entry - sl) > 0:
        sl_dist = abs(entry - sl) / entry
        risk_usd = bankroll * risk_pct / 100
        position = risk_usd / sl_dist
        lev = position / bankroll
        return max(2, min(50, round(lev)))
    scalp_tf = {"1m", "3m", "5m", "15m", "30m"}
    if timeframe in scalp_tf: return 20
    if rr >= 5.0: return 5
    if rr >= 3.0: return 7
    if rr >= 2.0: return 10
    return 15


def _net_return(entry: float, target: float, direction: str, leverage: int) -> float:
    if not entry: return 0.0
    price_move_pct = ((target - entry) / entry) if direction == "LONG" else ((entry - target) / entry)
    gross = price_move_pct * leverage * 100
    fee_cost = BLOFIN_TAKER_FEE * 2 * leverage * 100
    return gross - fee_cost


# ─── Formato VIP ───────────────────────────────────────────────────────────

def format_signal_message(signal: dict, analysis: str = "", ref_link: str = "",
                          mode: str = "swing", tier: str = "full",
                          recent_wins: int = 0, recent_losses: int = 0) -> str:
    """Sinal completo — mesmo formato para FREE e VIP."""
    return _format_full(signal, analysis, ref_link, mode, recent_wins, recent_losses)


def format_portfolio_header(signals: list, bias: str, ref_link: str = "") -> str:
    """Mensagem de abertura do portfolio diário com viés e estrutura de hedge."""
    n_longs  = sum(1 for s in signals if s.get("direction") == "LONG")
    n_shorts = sum(1 for s in signals if s.get("direction") == "SHORT")
    total    = n_longs + n_shorts
    if total == 0:
        return ""

    long_pct  = round(n_longs / total * 100)
    short_pct = 100 - long_pct
    net_exp   = long_pct - short_pct  # ex: +33% = net long

    bias_map = {
        "bullish": ("📈 ALTA", "🟢"),
        "bearish": ("📉 BAIXA", "🔴"),
        "neutro":  ("↔️ NEUTRO", "🟡"),
    }
    bias_label, bias_emoji = bias_map.get(bias, ("↔️ NEUTRO", "🟡"))

    net_label = f"+{net_exp}% long" if net_exp > 0 else f"{net_exp}% short" if net_exp < 0 else "neutro"

    # Risco total alocado (soma dos risk_pct de cada sinal)
    total_risk = round(sum(float(s.get("risk_pct", 1.5)) for s in signals), 1)

    # Timeframe majoritário
    tfs = [s.get("timeframe", "4H") for s in signals]
    main_tf = max(set(tfs), key=tfs.count)

    now = datetime.now(timezone.utc).strftime("%d/%m")
    weekday_names = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    weekday = weekday_names[datetime.now().weekday()]

    lines = [
        f"⚡ *{BRAND_NAME}* — PORTFOLIO {now} ({weekday})",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"{bias_emoji} Viés de mercado: *{bias_label}*",
        f"",
        f"├ {n_longs} operações LONG  ({long_pct}%)",
        f"└ {n_shorts} operações SHORT ({short_pct}%)",
        f"",
        f"📐 Hedge parcial — net exposure: `{net_label}`",
        f"⚠️ Risco total alocado: `{total_risk}% da banca`",
        f"⏱ Timeframe: `{main_tf}` _(swing/longo prazo)_",
        f"",
        f"_Estrutura: se acertar o viés você ganha nas {n_longs if bias == 'bullish' else n_shorts} posições maiores._",
        f"_Se errar, as {n_shorts if bias == 'bullish' else n_longs} posições opostas protegem parte da banca._",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{total} sinais abaixo 👇_",
    ]

    if ref_link:
        lines += [f"", f"🔗 [Abrir conta BloFin para operar]({ref_link})"]

    return "\n".join(lines)


def _pos_table(entry: float, sl: float, direction: str, risk_pct: float = 1.5,
               sizing_info: str = "") -> str:
    """Tabela de tamanho de posição com risco dinâmico do position sizer."""
    if not entry or not sl or entry == sl:
        return ""
    sl_pct = abs(entry - sl) / entry
    if sl_pct == 0:
        return ""
    bancas = [500, 1_000, 2_000, 5_000, 10_000]
    risk_label = f"{risk_pct:.1f}%"
    lines  = [f"*💰 QUANTO ENTRAR — risco {risk_label} da banca:*"]
    for b in bancas:
        pos  = round((b * risk_pct / 100) / sl_pct)
        risk = round(b * risk_pct / 100, 1)
        b_str   = f"${b:,.0f}".replace(",", ".")
        pos_str = f"${pos:,.0f}".replace(",", ".")
        lines.append(f"  `{b_str:<8}` → posição `{pos_str}`  _(risco ${risk})_")
    lines.append("_20% no A1 (+ move SL) · 50% no A2 · 30% no A3 (runner)_")
    if sizing_info:
        lines.append(f"_🧮 {sizing_info}_")
    return "\n".join(lines)


def _format_full(signal: dict, analysis: str, ref_link: str, mode: str,
                 recent_wins: int, recent_losses: int) -> str:
    direction  = signal["direction"]
    pair       = signal.get("pair", "N/A")
    tf         = signal.get("timeframe", "1H")
    entry      = signal.get("entry", 0)
    sl         = signal.get("stop_loss", 0)
    tp1        = signal.get("tp1", 0)
    tp2        = signal.get("tp2", 0)
    tp3        = signal.get("tp3", 0)
    confidence = signal.get("confidence", 0)

    dir_emoji = "🟢" if direction == "LONG" else "🔴"
    dir_label = "LONG  ↑" if direction == "LONG" else "SHORT  ↓"

    sl_dist = abs(entry - sl)
    rr = signal.get("rr_ratio", 0)
    if sl_dist > 0 and tp1 and tp2 and tp3:
        rr = round(
            abs(tp1 - entry) / sl_dist * 0.50 +
            abs(tp2 - entry) / sl_dist * 0.30 +
            abs(tp3 - entry) / sl_dist * 0.20, 2
        )

    # Variação % de cada nível em relação à entrada
    def _chg(price):
        if not entry: return 0.0
        return ((price - entry) / entry * 100) if direction == "LONG" else ((entry - price) / entry * 100)

    raw_setup   = signal.get("setup_type") or ("sniper" if rr >= 4.5 else mode)
    setup_label, setup_sub = SETUP_META.get(raw_setup, SETUP_META["scalp"])
    opening     = _opening_phrase(direction, raw_setup, recent_wins)
    conf_bar    = _confidence_bar(confidence)
    rr_label    = _rr_label(rr)
    now         = datetime.now(timezone.utc).strftime("%d/%m %H:%M UTC")
    footer      = _context_footer(recent_wins, recent_losses)
    risk_pct    = float(signal.get("risk_pct", 1.5))
    sizing_info = signal.get("sizing_info", "")
    pos_table   = _pos_table(entry, sl, direction, risk_pct=risk_pct, sizing_info=sizing_info)

    lines = [
        f"{BRAND_HEADER}  ·  *{setup_label}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{opening}_",
        f"",
        f"{dir_emoji} *{dir_label}*  `{pair}`  `{tf}`",
        f"_{setup_sub}_",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📍 *Entrada*      `{_fmt_price(entry)}`",
        f"🛑 *Stop Loss*   `{_fmt_price(sl)}`  _({_chg(sl):+.1f}%)_",
        f"──────────────────────────",
        f"🎯 *Alvo 1*       `{_fmt_price(tp1)}`  _({_chg(tp1):+.1f}%)_  · 20% + mover SL → breakeven",
        f"🎯 *Alvo 2*       `{_fmt_price(tp2)}`  _({_chg(tp2):+.1f}%)_  · fechar 50%",
        f"🏆 *Alvo 3*       `{_fmt_price(tp3)}`  _({_chg(tp3):+.1f}%)_  · deixar rodar 30%",
        f"",
        f"⚖️ R:R `{rr}:1` — {rr_label}  ·  📊 Conf: {conf_bar} {confidence}%",
        f"🕐 _{now}_",
        f"",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if pos_table:
        lines += [pos_table, f""]

    if analysis:
        safe = analysis.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")
        lines += [
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📈 *Análise:*",
            safe,
            f"",
        ]

    lines += [
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        footer,
    ]

    if ref_link:
        lines += [
            f"",
            f"🔗 [Abrir conta BloFin — opere esses sinais]({ref_link})",
        ]

    return "\n".join(lines)


# _format_free removido — FREE e VIP recebem o mesmo sinal completo.
# Diferenciação de valor: /ask (VIP ilimitado vs 3/dia FREE), /mentor, timing.


# ─── Update de trade (TP/SL hit) ──────────────────────────────────────────

def format_update_message(pair: str, event: str, trade: dict, bankroll: float = 1000.0) -> str:
    _close_pct = {"TP1_HIT": 50, "TP2_HIT": 30, "TP3_HIT": 20, "SL_HIT": 100}
    _remaining = {"TP1_HIT": 50, "TP2_HIT": 20, "TP3_HIT": 0,  "SL_HIT": 0}

    event_configs = {
        "TP1_HIT": ("🎯", "ALVO 1 ATINGIDO"),
        "TP2_HIT": ("🎯🎯", "ALVO 2 ATINGIDO"),
        "TP3_HIT": ("🏆", "ALVO FINAL — POSIÇÃO ENCERRADA"),
        "SL_HIT":  ("🛑", "STOP ATIVADO — POSIÇÃO ENCERRADA"),
    }
    emoji, label = event_configs.get(event, ("📢", event))

    entry      = trade.get("entry", 0)
    exit_price = trade.get("exit_price", trade.get("current_price", 0))
    pnl        = trade.get("pnl_pct", 0)
    direction  = trade.get("direction", "LONG")
    opened_at  = trade.get("opened_at", "")
    rr         = trade.get("rr_ratio", 0)
    remaining  = _remaining.get(event, 0)
    closed_now = _close_pct.get(event, 100)

    from modules.performance import PerformanceDB
    pnl_usd       = PerformanceDB.calc_pnl_usd(trade, bankroll)
    pnl_banca_pct = (pnl_usd / bankroll * 100) if bankroll else 0.0

    pnl_emoji = "✅" if pnl_usd >= 0 else "❌"
    usd_str   = f"+${pnl_usd:.2f}"       if pnl_usd >= 0       else f"-${abs(pnl_usd):.2f}"
    pct_str   = f"+{pnl_banca_pct:.2f}%" if pnl_banca_pct >= 0 else f"{pnl_banca_pct:.2f}%"
    move_str  = f"+{pnl:.3f}%"           if pnl >= 0           else f"{pnl:.3f}%"

    # Frase contextual por evento
    tp_phrases = {
        "TP1_HIT": [
            "✅ Primeiro alvo batido! Metade do lucro já garantido na conta.",
            "✅ TP1 atingido. Lucro parcial realizado — posição ainda aberta para mais.",
            "✅ Chegou no primeiro alvo. Já tá no verde, agora aguarda o próximo.",
            "✅ Parcial realizado. Quem entrou já está lucrando.",
        ],
        "TP2_HIT": [
            "✅✅ Segundo alvo batido! 80% da posição já fechada no lucro.",
            "✅✅ TP2 confirmado. Quase no alvo máximo.",
            "✅✅ Dois alvos batidos. Trade operando muito bem.",
        ],
        "TP3_HIT": [
            "🏆 TRADE COMPLETO! Todos os alvos batidos.",
            "🏆 Alvo máximo atingido. Trade fechado com resultado cheio.",
            "🏆 Três alvos, três acertos. Esse é o método.",
            "🏆 Missão cumprida. Posição encerrada no topo.",
        ],
        "SL_HIT": [
            "O stop foi ativado. Risco controlado, banca protegida — é assim que se gerencia.",
            "Stop executado. Perda limitada ao planejado. Próximo setup já em análise.",
            "Proteção ativada. Quem gerencia o risco, sobrevive no mercado.",
        ],
    }
    phrase = random.choice(tp_phrases.get(event, ["Evento registrado."]))

    lines = [
        f"{BRAND_HEADER}",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"{emoji} *{label}*",
        f"_{phrase}_",
        f"",
        f"📌 `{pair}` · {direction}",
        f"📍 Entrada: `{_fmt_price(entry)}`  →  Saída: `{_fmt_price(exit_price)}`  _({closed_now}%)_",
        f"",
        f"{pnl_emoji} *PNL acumulado: `{usd_str}`*  ·  `{pct_str} da banca`",
        f"_Movimento: {move_str}_",
    ]

    if rr:
        lines.append(f"⚖️ R:R executado: `{rr}:1`")

    if remaining > 0:
        lines += [f"", f"📊 *{remaining}% da posição ainda aberta*"]
    else:
        lines += [f"", f"🔒 *Posição encerrada*"]

    if opened_at:
        try:
            opened = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
            delta  = datetime.now(timezone.utc) - opened
            hours  = int(delta.total_seconds() // 3600)
            mins   = int((delta.total_seconds() % 3600) // 60)
            duration = f"{hours}h {mins}m" if hours else f"{mins}m"
            lines.append(f"⏱ Duração: {duration}")
        except Exception:
            pass

    lines += [f"", f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄", f"_{BRAND_TAG}_"]
    return "\n".join(lines)


# ─── Relatório semanal para leigo ─────────────────────────────────────────

def format_weekly_recap(stats: dict, starting_bankroll: float = 1000.0) -> str:
    """Relatório simples, emocional, pensado para quem não entende de trade."""
    wins          = stats.get("wins", 0)
    losses        = stats.get("losses", 0)
    total         = stats.get("total_trades", 0)
    wr            = stats.get("win_rate", 0.0)
    pnl_usd       = stats.get("total_pnl_usd", 0.0)
    cur_bankroll  = stats.get("current_bankroll", starting_bankroll)
    growth        = cur_bankroll - starting_bankroll
    growth_pct    = (growth / starting_bankroll * 100) if starting_bankroll else 0

    pnl_str    = f"+${pnl_usd:.2f}" if pnl_usd >= 0 else f"-${abs(pnl_usd):.2f}"
    growth_str = f"+{growth_pct:.1f}%" if growth >= 0 else f"{growth_pct:.1f}%"
    banca_str  = f"${cur_bankroll:.2f}"

    # Emoji de humor baseado no resultado
    if wr >= 70 and pnl_usd > 0:
        mood = "🔥"
        headline = "Semana muito boa."
    elif wr >= 55 and pnl_usd > 0:
        mood = "✅"
        headline = "Semana positiva."
    elif pnl_usd >= 0:
        mood = "📊"
        headline = "Semana equilibrada."
    else:
        mood = "📊"
        headline = "Semana de aprendizado."

    # Nunca mostra losses diretamente se semana foi ruim
    if pnl_usd >= 0:
        result_line = f"  {mood} *{wins} trades fecharam no verde*"
        if losses > 0:
            result_line += f"  ·  _{losses} operações protegidas pelo stop_"
    else:
        result_line = f"  📊 *{total} operações realizadas*"

    lines = [
        f"{BRAND_HEADER}",
        f"📅 *Resumo da Semana*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"_{headline}_",
        f"",
        result_line,
        f"  🎯 *Taxa de acerto:* {wr:.0f}%",
        f"  💰 *Resultado:* `{pnl_str}`",
        f"",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"💼 *Banca atual: `{banca_str}`*  ({growth_str} desde o início)",
        f"",
        f"_Quem seguiu os sinais essa semana,_",
        f"_seguiu o método. Isso é o que importa._",
        f"",
        f"_{BRAND_TAG}_",
    ]
    return "\n".join(lines)


# ─── Análise macro semanal (segunda-feira) ────────────────────────────────

def format_weekly_macro(
    macro_text: str,
    market_data: dict,
    conviction_signals: list,
    ref_link: str = "",
) -> str:
    """Mensagem de abertura de semana com análise macro + entradas de convicção."""

    btc_price  = market_data.get("btc_price", "?")
    eth_price  = market_data.get("eth_price", "?")
    btc_change = market_data.get("btc_change", 0.0)
    eth_change = market_data.get("eth_change", 0.0)
    bias       = market_data.get("bias", "neutro").upper()
    week       = market_data.get("week", datetime.now(timezone.utc).strftime("%d/%m"))

    btc_arrow  = "📈" if btc_change >= 0 else "📉"
    eth_arrow  = "📈" if eth_change >= 0 else "📉"
    bias_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRO": "⚪"}.get(bias, "⚪")

    # Sanitiza texto do LLM para Markdown Telegram
    safe_text = macro_text.replace("_", "\\_").replace("*", "\\*").replace("`", "\\`").replace("[", "\\[")

    lines = [
        f"{BRAND_HEADER}",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📅 *ABERTURA DE SEMANA — {week}*",
        f"",
        f"  {btc_arrow} *BTC:* `{btc_price}`  ({btc_change:+.1f}% 7d)",
        f"  {eth_arrow} *ETH:* `{eth_price}`  ({eth_change:+.1f}% 7d)",
        f"  {bias_emoji} *Viés macro:* `{bias}`",
        f"",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📝 *Leitura da Semana*",
        f"",
        safe_text,
    ]

    # Entradas de convicção
    if conviction_signals:
        lines += [
            f"",
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            f"🔒 *ENTRADAS DE CONVICÇÃO — ESSA SEMANA*",
            f"_Setups identificados no fim de semana. Aguardando confirmação._",
            f"",
        ]
        for sig in conviction_signals[:3]:
            pair      = sig.get("pair", "?")
            direction = sig.get("direction", "?")
            entry     = sig.get("entry", 0)
            sl        = sig.get("stop_loss", 0)
            tp1       = sig.get("tp1", 0)
            tp3       = sig.get("tp3", 0)
            rr        = sig.get("rr_ratio", 0)
            conf      = sig.get("confidence", 0)
            tf        = sig.get("timeframe", "4H")
            d_emoji   = "🟢" if direction == "LONG" else "🔴"
            d_label   = "LONG ↑" if direction == "LONG" else "SHORT ↓"
            lines += [
                f"{d_emoji} *{pair}* `{d_label}` · `{tf}`",
                f"  📍 Entrada: `{_fmt_price(entry)}`  ·  SL: `{_fmt_price(sl)}`",
                f"  🎯 TP1: `{_fmt_price(tp1)}`  →  TP3: `{_fmt_price(tp3)}`",
                f"  ⚖️ R:R `{rr}:1`  ·  Confiança: `{conf}%`",
                f"",
            ]

    lines += [
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"_Boa semana. Foco no método, não na emoção._",
        f"_{BRAND_TAG}_",
    ]

    if ref_link:
        lines.append(f"🔗 [Opere na BloFin]({ref_link})")

    return "\n".join(lines)


# ─── Stats ─────────────────────────────────────────────────────────────────

def _stats_block(label: str, stats: dict, starting_bankroll: float = 1000.0) -> list:
    total            = stats.get("total_trades", 0)
    wins             = stats.get("wins", 0)
    losses           = stats.get("losses", 0)
    wr               = stats.get("win_rate", 0.0)
    total_pnl_usd    = stats.get("total_pnl_usd", 0.0)
    current_bankroll = stats.get("current_bankroll", starting_bankroll)
    max_dd           = stats.get("max_drawdown", 0.0)
    max_dd_usd       = stats.get("max_drawdown_usd", 0.0)
    pf               = stats.get("profit_factor", 0.0)
    avg_win_usd      = stats.get("avg_win_usd", 0.0)
    avg_loss_usd     = stats.get("avg_loss_usd", 0.0)

    if total == 0:
        return [f"*{label}* — _sem dados_", ""]

    wr_bar    = _bar(round(wr / 10))
    pnl_emoji = "📈" if total_pnl_usd >= 0 else "📉"
    pnl_str   = f"+${total_pnl_usd:.2f}" if total_pnl_usd >= 0 else f"-${abs(total_pnl_usd):.2f}"
    pf_str    = f"{pf:.2f}" if pf != float("inf") else "∞"

    return [
        f"*{label}*",
        f"  📋 {total} trades  ·  ✅ {wins}W  ❌ {losses}L",
        f"  🎯 Win Rate: {wr_bar} {wr:.1f}%",
        f"  {pnl_emoji} PNL: `{pnl_str}`  ·  PF: `{pf_str}`",
        f"  💼 Banca: `${current_bankroll:.2f}`  ·  Max DD: `${max_dd_usd:.2f}` ({max_dd:.1f}%)",
        f"  💚 Avg Win: `+${avg_win_usd:.2f}`  ·  💔 Avg Loss: `${avg_loss_usd:.2f}`",
        "",
    ]


def format_stats_message(stats: dict, starting_bankroll: float = 1000.0) -> str:
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    if "weekly" in stats or "monthly" in stats or "annual" in stats:
        lines = [
            f"{BRAND_HEADER}",
            f"📊 *Relatório de Performance*",
            f"_Banca inicial: ${starting_bankroll:.0f}  ·  {now}_",
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            "",
        ]
        for label, key in [("📅 Semanal", "weekly"), ("📆 Mensal", "monthly"), ("🗓 Anual", "annual")]:
            if key in stats:
                lines += _stats_block(label, stats[key], starting_bankroll)
        lines.append(f"_{BRAND_TAG}_")
        return "\n".join(lines)

    # Single period
    total     = stats.get("total_trades", 0)
    wins      = stats.get("wins", 0)
    losses    = stats.get("losses", 0)
    wr        = stats.get("win_rate", 0.0)
    total_pnl = stats.get("total_pnl", 0.0)
    max_dd    = stats.get("max_drawdown", 0.0)
    pf        = stats.get("profit_factor", 0.0)
    avg_win   = stats.get("avg_win", 0.0)
    avg_loss  = stats.get("avg_loss", 0.0)

    wr_bar    = _bar(round(wr / 10))
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"
    pnl_str   = f"+{total_pnl:.2f}%" if total_pnl >= 0 else f"{total_pnl:.2f}%"

    return "\n".join([
        f"{BRAND_HEADER}",
        f"📊 *Performance — 30 dias*",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
        f"📋 {total} trades  ·  ✅ {wins}W  ❌ {losses}L",
        f"",
        f"🎯 *Win Rate:* {wr_bar} {wr:.1f}%",
        f"{pnl_emoji} *PNL:* `{pnl_str}`",
        f"",
        f"📐 *Profit Factor:* `{pf:.2f}`",
        f"📉 *Max Drawdown:* `{max_dd:.1f}%`",
        f"",
        f"💚 *Avg Win:* `+{avg_win:.2f}%`  ·  💔 *Avg Loss:* `{avg_loss:.2f}%`",
        f"",
        f"_{BRAND_TAG}_",
    ])


def format_trades_list(trades: list, current_bankroll: float = 0.0,
                       realized_pnl: float = 0.0, unrealized_pnl: float = 0.0,
                       starting_bankroll: float = 1000.0) -> str:
    if not trades:
        return f"📭 *Nenhum trade ativo no momento.*\n\n_{BRAND_TAG}_"

    lines = [
        f"{BRAND_HEADER}",
        f"📋 *Trades Ativos* ({len(trades)})",
        f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
    ]

    for t in trades:
        emoji   = "🟢" if t["direction"] == "LONG" else "🔴"
        entry   = t.get("entry", 0)
        current = t.get("current_price", entry)
        unreal  = t.get("unrealized_usd", 0.0)
        unreal_pct = (unreal / starting_bankroll * 100) if starting_bankroll else 0.0
        u_str   = f"+${unreal:.2f}" if unreal >= 0 else f"-${abs(unreal):.2f}"
        up_str  = f"+{unreal_pct:.2f}%" if unreal_pct >= 0 else f"{unreal_pct:.2f}%"
        u_icon  = "📈" if unreal >= 0 else "📉"

        tp_status = ""
        if t.get("tp1_hit"): tp_status += "TP1✅ "
        if t.get("tp2_hit"): tp_status += "TP2✅ "

        lines.append(
            f"{emoji} *`{t['pair']}`* — {t['direction']}  {tp_status}\n"
            f"   📍 `{_fmt_price(entry)}`  →  atual `{_fmt_price(current)}`\n"
            f"   {u_icon} Não realizado: `{u_str}` ({up_str})"
        )

    if current_bankroll:
        banca_change = current_bankroll - starting_bankroll
        b_emoji = "📈" if banca_change >= 0 else "📉"
        b_str   = f"+${banca_change:.2f}" if banca_change >= 0 else f"-${abs(banca_change):.2f}"
        lines += [
            f"",
            f"┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄",
            f"💼 *Banca: `${current_bankroll:.2f}`* {b_emoji} `{b_str}`",
            f"_Realizado: ${realized_pnl:+.2f}  ·  Aberto: ${unrealized_pnl:+.2f}_",
        ]

    lines.append(f"\n_{BRAND_TAG}_")
    return "\n".join(lines)
