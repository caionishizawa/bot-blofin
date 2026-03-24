"""
LLM Analyst — scalp, swing, e análise macro semanal.
"""

import os
from datetime import datetime, timezone


# ─── Scalp prompt — trader experiente, tom humano e direto ──────────────────
SCALP_PROMPT = """Você é um analista sênior de cripto do canal sideradogcripto. Sua análise é lida por traders leigos que querem entender o trade de forma clara, confiante e sofisticada. Escreva em português, sem markdown, sem asterisco, sem cabeçalho. Tom: profissional mas humano.

SETUP COMPLETO — {pair} {direction} {timeframe}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Entrada: {entry}
Stop Loss: {stop_loss}
TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
R:R ponderado: {rr_ratio}:1
Confiança: {confidence}%

CONTEXTO TÉCNICO
RSI: {rsi:.0f} | ADX: {adx:.0f}
Suporte relevante: {support:.4f}
Resistência relevante: {resistance:.4f}
Order Block: {orderblock}
Divergência RSI: {rsi_div}
Confluências ativas: {reasons}

Escreva EXATAMENTE 5 linhas de texto corrido, sem numeração:
1. O que o preço está fazendo agora — contexto de mercado, onde está em relação às zonas
2. Quais indicadores se alinham e o que isso sinaliza para o movimento esperado
3. Por que esse nível de entrada faz sentido — a lógica por trás do setup
4. Onde o trade invalida — nível exato e o que isso significaria para o cenário
5. Conclusão direta — executar agora, aguardar confirmação ou evitar. Seja decisivo.
"""


# ─── Swing prompt — voz humana, jovem, estilo sideradogcripto ──────────────
SWING_PROMPT = """Você é o sideradog — trader jovem com método próprio que posta análises reais no seu canal de cripto. Primeira pessoa, tom pessoal, direto e confiante. Português. Sem markdown, sem asterisco.

SETUP SWING — {pair} {direction}
Entrada: {entry} | Stop: {stop_loss} | R:R {rr_ratio}:1
Alvos: TP1 {tp1} | TP2 {tp2} | TP3 {tp3}
RSI: {rsi:.0f} | Confiança: {confidence}%
Zonas: suporte {support:.4f} / resistência {resistance:.4f}
Order Block: {orderblock}
Confluências: {reasons}

Escreva EXATAMENTE 5 linhas em primeira pessoa:
1. O que me chamou atenção nesse setup — o que eu vi primeiro
2. A estrutura técnica completa que justifica a entrada
3. O contexto de mercado maior — onde esse par está no ciclo
4. Onde eu corto se errar — nível e por que é o ponto de invalidação
5. Uma frase de fechamento confiante no meu estilo — sem exagero, com convicção
"""


# ─── Macro weekly prompt ────────────────────────────────────────────────────
MACRO_PROMPT = """Você é o sideradog — analista e trader do canal sideradogcripto. É segunda-feira e você vai abrir a semana com sua leitura macro do mercado cripto. Tom pessoal, direto, confiante. Português. Sem markdown, sem asterisco, sem listas numeradas.

CONTEXTO DE MERCADO — SEMANA {week}
━━━━━━━━━━━━━━━━━━━━━━━━━━
BTC: preço {btc_price} | RSI {btc_rsi:.0f} | tendência {btc_trend} | var 7d {btc_change:+.1f}%
ETH: preço {eth_price} | RSI {eth_rsi:.0f} | tendência {eth_trend} | var 7d {eth_change:+.1f}%
SOL: preço {sol_price} | RSI {sol_rsi:.0f} | tendência {sol_trend}
Dominância BTC estimada: {btc_dominance}
Pares em tendência de alta: {bullish_count}/{total_pairs}
Pares em tendência de baixa: {bearish_count}/{total_pairs}
Setups de alta qualidade identificados: {conviction_count}

Escreva exatamente 6 frases separadas por linha. Sem prefixos, sem numeração, sem "Linha", sem títulos. Apenas 6 frases diretas:
- O que o mercado mostrou e o que isso muda agora
- Leitura do BTC: zona, o que estou vendo
- ETH e alts: alinhadas ou divergindo?
- Viés da semana em uma frase — bullish, bearish ou neutro
- O que foco essa semana: setups e pares
- Fecho curto e confiante — uma frase, sem exagero
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
      2. MLX local (mlx-community/Qwen2.5-7B-Instruct-4bit, Apple Silicon)
      3. Ollama local (se rodando em localhost:11434)
      4. Fallback gerado por código
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    if api_key:
        try:
            return await _analyze_with_claude(signal, api_key, mode)
        except Exception as e:
            print(f"LLM analysis failed (Claude): {e}")

    # Tenta MLX local (Apple Silicon nativo)
    try:
        return await _analyze_with_mlx(signal, mode=mode)
    except Exception as e:
        print(f"LLM analysis failed (MLX): {e}")

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
        model="claude-opus-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


_mlx_model = None
_mlx_tokenizer = None
_MLX_MODEL_ID = "mlx-community/Qwen2.5-7B-Instruct-4bit"


async def _analyze_with_mlx(signal: dict, mode: str = "scalp") -> str:
    """Inferência local via MLX (Apple Silicon). Carrega modelo uma vez e reutiliza."""
    import asyncio
    from functools import partial

    global _mlx_model, _mlx_tokenizer
    if _mlx_model is None:
        from mlx_lm import load
        print(f"[MLX] Carregando {_MLX_MODEL_ID}...")
        _mlx_model, _mlx_tokenizer = load(_MLX_MODEL_ID)
        print("[MLX] Modelo pronto.")

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

    from mlx_lm import generate as mlx_generate
    loop = asyncio.get_event_loop()
    fn = partial(mlx_generate, _mlx_model, _mlx_tokenizer, prompt=prompt, max_tokens=250, verbose=False)
    result = await loop.run_in_executor(None, fn)
    # Remove eventual echo do prompt
    if prompt[:30] in result:
        result = result[len(prompt):]
    # Remove tokens especiais e continuação do modelo
    for stop in ["<|endoftext|>", "<|im_end|>", "\nHuman:", "\nUser:", "\nAssistant:"]:
        if stop in result:
            result = result[:result.index(stop)]
    return result.strip()


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


async def analyze_weekly_macro(market_data: dict, api_key: str = None) -> str:
    """Gera análise macro semanal para segunda-feira.

    market_data deve conter:
      btc_price, btc_rsi, btc_trend, btc_change,
      eth_price, eth_rsi, eth_trend, eth_change,
      sol_price, sol_rsi, sol_trend,
      btc_dominance, bullish_count, bearish_count, total_pairs,
      conviction_count, week
    """
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    prompt = MACRO_PROMPT.format(**market_data)

    if api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            message = await client.messages.create(
                model="claude-opus-4-6",
                max_tokens=600,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text.strip()
        except Exception as e:
            print(f"Macro analysis failed (Claude): {e}")

    # MLX local
    try:
        import asyncio
        from functools import partial
        global _mlx_model, _mlx_tokenizer
        if _mlx_model is None:
            from mlx_lm import load
            _mlx_model, _mlx_tokenizer = load(_MLX_MODEL_ID)
        from mlx_lm import generate as mlx_generate
        loop = asyncio.get_event_loop()
        fn = partial(mlx_generate, _mlx_model, _mlx_tokenizer,
                     prompt=prompt, max_tokens=600, verbose=False)
        result = await loop.run_in_executor(None, fn)
        for stop in ["<|endoftext|>", "<|im_end|>", "\nHuman:", "\nUser:"]:
            if stop in result:
                result = result[:result.index(stop)]
        return _clean_macro_text(result)
    except Exception as e:
        print(f"Macro analysis failed (MLX): {e}")

    # Fallback textual
    bias = "bullish" if market_data.get("bullish_count", 0) > market_data.get("bearish_count", 0) else "bearish"
    return (
        f"Abrindo a semana com viés {bias}. BTC em {market_data.get('btc_price','?')} "
        f"com RSI {market_data.get('btc_rsi',50):.0f} — "
        f"{'momentum positivo' if float(str(market_data.get('btc_rsi',50))) < 60 else 'zona de atenção'}. "
        f"Foco nos setups de maior qualidade essa semana."
    )


def _clean_macro_text(text: str) -> str:
    """Remove prefixos que o modelo pode gerar (Linha 1:, 1., etc.)."""
    import re
    lines = text.strip().split("\n")
    cleaned = []
    for line in lines:
        line = re.sub(r"^(Linha\s*\d+\s*:?\s*|^\d+\.\s*)", "", line.strip())
        if line:
            cleaned.append(line)
    return "\n".join(cleaned)


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
