"""
LLM Analyst — Claude AI integration for trade analysis in PT-BR.
"""

import os


ANALYSIS_PROMPT = """Você é um analista técnico profissional de criptomoedas.
Analise o seguinte sinal de trading e forneça uma análise concisa em português:

Par: {pair}
Direção: {direction}
Entry: {entry}
Stop Loss: {stop_loss}
TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
Confluências ({score}): {reasons}
Confiança: {confidence}%
Risk:Reward: {rr_ratio}:1

Forneça:
1. Análise do setup (2-3 frases)
2. Pontos fortes e fracos
3. Recomendação final (entrada recomendada ou aguardar)
"""


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
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


def _fallback_analysis(signal: dict) -> str:
    """Generate template-based analysis without LLM."""
    direction = signal.get("direction", "N/A")
    pair = signal.get("pair", "N/A")
    confidence = signal.get("confidence", 0)
    score = signal.get("score", 0)
    rr = signal.get("rr_ratio", 0)
    reasons = signal.get("reasons", [])

    strength = "forte" if confidence >= 70 else "moderado" if confidence >= 50 else "fraco"

    lines = [
        f"📊 Análise — {pair} {direction}",
        f"",
        f"Setup {strength} com {score:.0f} confluências.",
        f"R:R de {rr}:1 — {'favorável' if rr >= 2 else 'aceitável' if rr >= 1.5 else 'baixo'}.",
        f"",
        f"Confluências:",
    ]
    for r in reasons:
        lines.append(f"  • {r}")

    if confidence >= 60 and rr >= 1.5:
        lines.append(f"\n✅ Entrada recomendada com gestão de risco.")
    else:
        lines.append(f"\n⚠️ Aguardar melhor confirmação.")

    return "\n".join(lines)
