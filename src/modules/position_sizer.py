"""
Position Sizer Dinâmico — calcula o % da banca a arriscar por trade.

Combina três fatores:
  1. Qualidade do setup    (confidence × RR)
  2. Momentum recente      (anti-martingale: aumenta no streak, reduz em drawdown)
  3. Proteção de capital   (corte agressivo se drawdown > 5%)

Fórmula:
  risk = BASE × qualidade × streak_mult × drawdown_mult
  clamped: [MIN_RISK, MAX_RISK]

Parâmetros ajustáveis pelo operador:
  BASE_RISK      1.5%   — ponto neutro (sem histórico, setup mediano)
  MIN_RISK       0.5%   — floor (nunca abaixo disso)
  MAX_RISK       4.0%   — teto (nunca acima disso)
"""

import logging

logger = logging.getLogger(__name__)

# ── Parâmetros do sistema ────────────────────────────────────────────────────
BASE_RISK = 1.5   # % neutro
MIN_RISK  = 0.5   # floor absoluto
MAX_RISK  = 4.0   # teto absoluto

# Limites de drawdown (% da banca) que ativam cortes
_DD_LIGHT    = 5.0   # -25% do risco base
_DD_MODERATE = 10.0  # -50%
_DD_SEVERE   = 15.0  # modo defensivo: MAX = 0.75%


def calculate_risk_pct(signal: dict, sizing_stats: dict) -> tuple[float, str]:
    """
    Retorna (risk_pct, motivo_legível).

    signal: dict com 'confidence' (int 0-100) e 'rr_ratio' (float)
    sizing_stats: dict de get_sizing_stats() com:
        current_streak   — int (+ wins, - losses)
        drawdown_pct     — float (% drawdown últimos 30d)
        win_rate_recent  — float (% win últimos 20 trades)
        total_closed     — int (trades fechados no histórico)
    """
    conf      = float(signal.get("confidence", 75))
    rr        = float(signal.get("rr_ratio", 2.0))
    streak    = int(sizing_stats.get("current_streak", 0))
    dd_pct    = float(sizing_stats.get("drawdown_pct", 0.0))
    total     = int(sizing_stats.get("total_closed", 0))

    # ── 1. QUALIDADE DO SETUP ────────────────────────────────────────────────
    # Confidence: baseline 80%. Abaixo reduz, acima aumenta.
    conf_mult = 0.70 + (conf / 100) * 0.60   # range: [0.70, 1.30]

    # RR: baseline 2.0. Abaixo corta, acima bônus (capped em RR=4.0).
    rr_norm   = min(rr / 2.0, 2.0)           # normaliza: RR2=1.0x, RR4=2.0x
    rr_mult   = 0.80 + rr_norm * 0.25        # range: [0.80, 1.30]

    quality   = conf_mult * rr_mult           # combinado: ~[0.56, 1.69]

    # ── 2. STREAK (ANTI-MARTINGALE) ─────────────────────────────────────────
    # Vitórias seguidas: +5% por win (máx +30%)
    # Perdas seguidas:   -12% por loss (máx -36%)
    # Sem histórico suficiente: neutro
    if total < 5:
        streak_mult = 1.0   # sem dados suficientes, não aplica
    elif streak >= 1:
        bonus = min(streak * 0.05, 0.30)
        streak_mult = 1.0 + bonus
    elif streak <= -1:
        penalty = min(abs(streak) * 0.12, 0.36)
        streak_mult = 1.0 - penalty
    else:
        streak_mult = 1.0

    # ── 3. PROTEÇÃO DE DRAWDOWN ─────────────────────────────────────────────
    if dd_pct >= _DD_SEVERE:
        dd_mult  = 0.33   # modo defensivo — risco ~0.5%
        dd_label = f"DEFENSIVO dd={dd_pct:.1f}%"
    elif dd_pct >= _DD_MODERATE:
        dd_mult  = 0.50
        dd_label = f"dd={dd_pct:.1f}%"
    elif dd_pct >= _DD_LIGHT:
        dd_mult  = 0.75
        dd_label = f"dd={dd_pct:.1f}%"
    else:
        dd_mult  = 1.0
        dd_label = ""

    # ── CÁLCULO FINAL ────────────────────────────────────────────────────────
    risk = BASE_RISK * quality * streak_mult * dd_mult
    risk = round(max(MIN_RISK, min(risk, MAX_RISK)), 2)

    # Monta label legível
    streak_label = ""
    if streak >= 2:
        streak_label = f"+{streak}W"
    elif streak <= -2:
        streak_label = f"{streak}L"

    parts = [f"conf={conf:.0f}%", f"RR={rr:.1f}"]
    if streak_label:
        parts.append(streak_label)
    if dd_label:
        parts.append(dd_label)
    reason = f"risk={risk}% [{', '.join(parts)}]"

    logger.info(
        f"PositionSizer: {reason} "
        f"(q={quality:.2f} s={streak_mult:.2f} dd={dd_mult:.2f})"
    )
    return risk, reason
