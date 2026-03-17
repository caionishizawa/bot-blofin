"""
LLM Analyst — Claude AI integration for trade analysis in PT-BR.
"""

import os


ANALYSIS_PROMPT = """Você é um analista técnico profissional de criptomoedas especializado em futuros.
Analise o sinal abaixo e responda APENAS em texto simples, sem markdown, sem headers, sem tabelas.

Par: {pair}
Direção: {direction}
Entrada: {entry}
Stop Loss: {stop_loss}
TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
Confluências ({score}): {reasons}
Confiança: {confidence}%
Risco/Retorno: {rr_ratio}:1

Responda em 3 parágrafos curtos, máximo 3 linhas cada:
1. Setup: explique o setup técnico e por que este é um bom momento de entrada
2. Gestão: comente sobre os níveis de saída e gestão de risco
3. Recomendação: entrada recomendada OU aguardar, com justificativa de 1 linha

IMPORTANTE: não use # * _ ` | ou qualquer formatação markdown. Apenas texto limpo."""


async def analyze_signal(signal: dict, api_key: str = None) -> str:
    """Analyze a trading signal using Claude AI.

    Falls back to template-based analysis if no API key.
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return await _analyze_with_claude(signal, api_key)
        except Exception as e:
            print(f"LLM analysis failed, using fallback: {e}")

    return _fallback_analysis(signal)


async def _analyze_with_claude(signal: dict, api_key: str) -> str:
    """Call Claude API for analysis."""
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=api_key)
    prompt = ANALYSIS_PROMPT.format(
        pair=signal.get("pair", "N/A"),
        direction=signal.get("direction", "N/A"),
        entry=signal.get("entry", 0),
        stop_loss=signal.get("stop_loss", 0),
        tp1=signal.get("tp1", 0),
        tp2=signal.get("tp2", 0),
        tp3=signal.get("tp3", 0),
        score=signal.get("score", 0),
        reasons=", ".join(signal.get("reasons", [])),
        confidence=signal.get("confidence", 0),
        rr_ratio=signal.get("rr_ratio", 0),
    )

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


def _fallback_analysis(signal: dict) -> str:
    """Generate template-based analysis without LLM."""
    direction = signal.get("direction", "N/A")
    pair = signal.get("pair", "N/A")
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio", 0)
    reasons = signal.get("reasons", [])
    score = signal.get("score", 0)

    strength = "forte" if confidence >= 70 else "moderado" if confidence >= 50 else "fraco"
    rr_str = "favorável" if rr >= 2 else "aceitável" if rr >= 1.5 else "baixo"

    confluences = ", ".join(reasons[:3]) if reasons else "indicadores alinhados"

    lines = [
        f"Setup {strength} em {pair} com {score:.0f} confluências técnicas: {confluences}.",
        f"",
        f"R:R de {rr}:1 é {rr_str}. Stop calibrado pelo ATR garante saída controlada.",
        f"",
    ]

    if confidence >= 60 and rr >= 1.5:
        lines.append(f"Entrada recomendada com gestão de risco. Parcial no TP1, mover stop para entrada.")
    else:
        lines.append(f"Aguardar melhor confirmação antes de entrar.")

    return "\n".join(lines)
