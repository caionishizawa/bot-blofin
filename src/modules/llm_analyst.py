"""
LLM Analyst — two modes: scalp (senior analyst, clinical) and swing (human, personal voice).
"""

import os
from datetime import datetime, timezone


# ─── Scalp prompt — trader experiente, tom humano e direto ──────────────────
SCALP_PROMPT = """Você é um trader experiente de cripto que escreve análises curtas e diretas em português.
Analise o setup abaixo e escreva 4 linhas naturais, como alguém que realmente opera isso.
Sem markdown, sem asterisco, sem cabeçalho. Fale com convicção mas sem exagero.

Setup:
Par: {pair} | {direction} | Timeframe: {timeframe}
Entrada: {entry} | Stop: {stop_loss} | R:R {rr_ratio}:1
Alvos: TP1 {tp1} | TP2 {tp2} | TP3 {tp3}
Indicadores ativos: {reasons}
RSI: {rsi:.0f} | ADX: {adx:.0f} | Confiança: {confidence}%
Suporte: {support:.4f} | Resistência: {resistance:.4f}
Orderblock: {orderblock}
Divergência RSI: {rsi_div}

Escreva exatamente 4 linhas de texto puro:
- Linha 1: o que o preço está fazendo agora em relação aos níveis chave
- Linha 2: quais indicadores estão alinhados e por que isso importa
- Linha 3: onde o setup quebra (nível de invalidação)
- Linha 4: sua conclusão — executar agora, aguardar, ou evitar
"""


# ─── Swing prompt — voz humana, jovem, seu estilo ────────────────────────────
SWING_PROMPT = """Você é um trader jovem que posta análises no seu canal de cripto. Escreve em primeira pessoa, tom pessoal e direto. Em português, sem markdown, sem asterisco.

Setup swing:
Par: {pair} | {direction}
Entrada: {entry} | Stop: {stop_loss} | R:R {rr_ratio}:1
Alvos: TP1 {tp1} | TP2 {tp2} | TP3 {tp3}
Suporte: {support:.4f} | Resistência: {resistance:.4f}
Orderblock: {orderblock}
RSI: {rsi:.0f} | Confiança: {confidence}%
Confluências: {reasons}

Escreva exatamente 4 linhas em primeira pessoa, como se você tivesse postado manualmente:
- Linha 1: por que você entrou nesse trade — o que você viu
- Linha 2: a estrutura técnica que justifica
- Linha 3: onde você corta se errar
- Linha 4: uma frase de fechamento no seu estilo, confiante
"""


def _extract_context(signal: dict) -> dict:
    """Extract S/R levels, orderblock, and RSI divergence from candle data."""
    df = signal.get("candles_df")
    context = {
        "support": signal.get("stop_loss", 0),
        "resistance": signal.get("tp2", 0),
        "orderblock": "não identificado",
        "rsi_div": "sem divergência",
        "rsi": 50.0,
        "adx": 20.0,
    }

    if df is None or df.empty or len(df) < 20:
        return context

    last = df.iloc[-1]

    # RSI and ADX
    if "rsi" in df.columns:
        context["rsi"] = float(last.get("rsi", 50))
    if "adx" in df.columns:
        context["adx"] = float(last.get("adx", 20))

    # S/R: recent swing high/low over last 20 candles
    window = df.tail(30)
    context["resistance"] = float(window["high"].max())
    context["support"] = float(window["low"].min())

    # Orderblock: last strong impulse candle (body > 1.8x avg body size)
    bodies = (df["close"] - df["open"]).abs()
    avg_body = bodies.rolling(20).mean().iloc[-1]
    last_20 = df.tail(20)
    strong = last_20[bodies.tail(20) > avg_body * 1.8]
    if not strong.empty:
        ob = strong.iloc[-1]
        ob_dir = "alta" if ob["close"] > ob["open"] else "baixa"
        context["orderblock"] = f"OB de {ob_dir} em {ob['close']:,.4f}"

    # RSI divergence: price higher high but RSI lower high (bearish div) or vice versa
    if "rsi" in df.columns and len(df) >= 10:
        recent = df.tail(10)
        price_trend = recent["close"].iloc[-1] - recent["close"].iloc[0]
        rsi_trend = recent["rsi"].iloc[-1] - recent["rsi"].iloc[0]
        if price_trend > 0 and rsi_trend < -5:
            context["rsi_div"] = "divergência bearish (preço subindo, RSI caindo)"
        elif price_trend < 0 and rsi_trend > 5:
            context["rsi_div"] = "divergência bullish (preço caindo, RSI subindo)"

    return context


async def analyze_signal(signal: dict, api_key: str = None, mode: str = "scalp") -> str:
    """Analyze a trading signal. mode='scalp' or 'swing'.

    Ordem de tentativa:
      1. Anthropic API (se ANTHROPIC_API_KEY definida e com crédito)
      2. Ollama local (se rodando em localhost:11434)
      3. Fallback gerado por código
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return await _analyze_with_claude(signal, api_key, mode)
        except Exception as e:
            print(f"LLM analysis failed (Claude): {e}")

    # Tenta Ollama local
    ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2")
    try:
        return await _analyze_with_ollama(signal, model=ollama_model, mode=mode)
    except Exception as e:
        print(f"LLM analysis failed (Ollama): {e}")

    return _fallback_analysis(signal, mode)


async def _analyze_with_claude(signal: dict, api_key: str, mode: str) -> str:
    import anthropic

    ctx = _extract_context(signal)
    template = SWING_PROMPT if mode == "swing" else SCALP_PROMPT

    prompt = template.format(
        pair=signal.get("pair", "N/A"),
        direction=signal.get("direction", "N/A"),
        timeframe=signal.get("timeframe", "1H"),
        entry=signal.get("entry", 0),
        stop_loss=signal.get("stop_loss", 0),
        tp1=signal.get("tp1", 0),
        tp2=signal.get("tp2", 0),
        tp3=signal.get("tp3", 0),
        rr_ratio=signal.get("rr_ratio", 0),
        confidence=signal.get("confidence", 0),
        reasons=", ".join(signal.get("reasons", [])),
        rsi=ctx["rsi"],
        adx=ctx["adx"],
        support=ctx["support"],
        resistance=ctx["resistance"],
        orderblock=ctx["orderblock"],
        rsi_div=ctx["rsi_div"],
    )

    client = anthropic.AsyncAnthropic(api_key=api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


async def _analyze_with_ollama(signal: dict, model: str = "llama3.2", mode: str = "scalp") -> str:
    """Chama Ollama local via HTTP (não precisa de biblioteca extra)."""
    import aiohttp, json

    ctx = _extract_context(signal)
    template = SWING_PROMPT if mode == "swing" else SCALP_PROMPT
    prompt = template.format(
        pair=signal.get("pair", "N/A"),
        direction=signal.get("direction", "N/A"),
        timeframe=signal.get("timeframe", "1H"),
        entry=signal.get("entry", 0),
        stop_loss=signal.get("stop_loss", 0),
        tp1=signal.get("tp1", 0),
        tp2=signal.get("tp2", 0),
        tp3=signal.get("tp3", 0),
        rr_ratio=signal.get("rr_ratio", 0),
        confidence=signal.get("confidence", 0),
        reasons=", ".join(signal.get("reasons", [])),
        rsi=ctx["rsi"],
        adx=ctx["adx"],
        support=ctx["support"],
        resistance=ctx["resistance"],
        orderblock=ctx["orderblock"],
        rsi_div=ctx["rsi_div"],
    )

    payload = {"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": 200}}
    async with aiohttp.ClientSession() as session:
        async with session.post("http://localhost:11434/api/generate", json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return data["response"].strip()


def _fallback_analysis(signal: dict, mode: str = "scalp") -> str:
    ctx = _extract_context(signal)
    reasons = signal.get("reasons", [])
    rr = signal.get("rr_ratio", 0)
    confidence = signal.get("confidence", 0)
    direction = signal.get("direction", "LONG")
    pair = signal.get("pair", "")

    conf_str = ", ".join(reasons[:3]) if reasons else "indicadores alinhados"
    action = "Entrada válida agora." if confidence >= 70 else "Aguardar confirmação."

    if mode == "swing":
        bias = "alta" if direction == "LONG" else "baixa"
        return (
            f"Tô de olho nesse {pair} pra swing, estrutura de {bias} se formando."
            f"\n{conf_str}. R:R {rr}:1 — vale o risco."
            f"\nInvalida se fechar fora do SL. Simples assim."
            f"\nAlvos definidos, risco controlado. Vamos."
        )

    return (
        f"Preço em zona relevante — S: {ctx['support']:,.4f} / R: {ctx['resistance']:,.4f}."
        f"\n{conf_str}."
        f"\nInvalida abaixo do SL. {action}"
    )
