"""
LLM Analyst — Claude AI integration for trade analysis in PT-BR.
"""

import os


ANALYSIS_PROMPT = """Analista técnico de cripto. Responda SOMENTE em texto limpo, sem markdown.

Par: {pair} | {direction} | Entrada: {entry} | SL: {stop_loss}
TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
Confluências: {reasons}
Confiança: {confidence}% | R:R {rr_ratio}:1

Responda em NO MÁXIMO 3 linhas curtas:
Linha 1: confluências presentes (só os nomes, ex: "EMA cross, MACD bullish, ADX 31")
Linha 2: nível crítico a observar (suporte/resistência chave ou condição de invalidação)
Linha 3: entrada agora ou aguardar — uma frase direta

Sem explicações. Só fatos e o trade."""


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
        reasons=", ".join(signal.get("reasons", [])),
        confidence=signal.get("confidence", 0),
        rr_ratio=signal.get("rr_ratio", 0),
    )

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


def _fallback_analysis(signal: dict) -> str:
    """Generate template-based analysis without LLM."""
    reasons = signal.get("reasons", [])
    confidence = signal.get("confidence", 0)
    rr = signal.get("rr_ratio", 0)

    confluences = ", ".join(reasons) if reasons else "indicadores alinhados"
    action = "Entrada agora." if confidence >= 60 and rr >= 1.5 else "Aguardar confirmação."

    return f"{confluences}\n{action}"
