"""
Agente Educacional — responde dúvidas de trading usando o conhecimento do sideradog.

FREE: Claude Haiku, 3 perguntas/dia
VIP:  Claude Sonnet, ilimitado, contexto expandido
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_KNOWLEDGE_BASE: str | None = None
_KB_PATH = Path(__file__).parent / "knowledge_base.md"


def _load_knowledge_base() -> str:
    global _KNOWLEDGE_BASE
    if _KNOWLEDGE_BASE is None:
        try:
            _KNOWLEDGE_BASE = _KB_PATH.read_text(encoding="utf-8")
        except Exception as e:
            logger.warning(f"Erro ao carregar knowledge base: {e}")
            _KNOWLEDGE_BASE = "Base de conhecimento não disponível no momento."
    return _KNOWLEDGE_BASE


def _build_system_prompt(user_memory: dict, recent_signals: list, is_vip: bool) -> str:
    level = user_memory.get("level", "iniciante")
    last_topics = user_memory.get("last_topics", [])
    total_asks = user_memory.get("total_asks", 0)

    kb = _load_knowledge_base()

    # Contexto dos sinais recentes (últimos 3)
    signals_ctx = ""
    if recent_signals:
        lines = ["Sinais recentes do bot (use como exemplos práticos quando relevante):"]
        for s in recent_signals[:3]:
            pair = s.get("pair", "")
            direction = s.get("direction", "")
            rr = s.get("rr_ratio", 0)
            confidence = s.get("confidence", 0)
            status = s.get("status", "")
            pnl = s.get("pnl_pct", 0)
            lines.append(
                f"  • {pair} {direction} | conf={confidence}% | RR={rr} | status={status}"
                + (f" | PNL={pnl:+.1f}%" if pnl != 0 else "")
            )
        signals_ctx = "\n".join(lines)

    # Contexto da memória do usuário
    memory_ctx = ""
    if total_asks > 0:
        memory_ctx = f"\nEste usuário já fez {total_asks} pergunta(s)."
        if last_topics:
            recent = last_topics[:3]
            memory_ctx += f" Tópicos recentes: {', '.join(recent)}."

    # Instrução de profundidade por tier
    if is_vip:
        depth_instruction = (
            "Este é um usuário VIP. Pode dar respostas mais detalhadas e técnicas. "
            "Pode usar termos avançados e ir mais fundo na explicação."
        )
    else:
        depth_instruction = (
            "Este é um usuário FREE. Respostas claras, diretas, máximo 4 parágrafos. "
            "Use linguagem simples. No final, mencione sutilmente que VIP tem acesso ilimitado e respostas mais completas."
        )

    # Instrução de nível
    if level == "iniciante":
        level_instruction = "O usuário é iniciante. Explique conceitos básicos quando necessário. Evite jargão sem explicação."
    elif level == "intermediario":
        level_instruction = "O usuário tem nível intermediário. Pode ir direto ao ponto sem explicar o básico."
    else:
        level_instruction = "O usuário é avançado. Pode usar linguagem técnica e exemplos complexos."

    system = f"""Você é o assistente educacional do @sideradogcripto — trader e criador de conteúdo de cripto.

Seu nome é SidAgent. Você responde dúvidas de trading com base no conhecimento e estilo do sideradog.
Você faz parte do bot de sinais SidQuant (@SidQuantBot).

{level_instruction}
{depth_instruction}
{memory_ctx}

REGRAS OBRIGATÓRIAS:
1. Responda SEMPRE em português brasileiro, de forma direta e prática.
2. Use o conhecimento e estilo do sideradog da base abaixo.
3. Cite exemplos reais dos sinais quando for útil.
4. Se não souber algo específico, seja honesto.
5. NUNCA recomende comprar ou vender ativos específicos agora. Apenas explique conceitos.
6. SEMPRE termine a resposta com o disclaimer: "⚠️ Não é recomendação de investimento."
7. Se a pergunta não for sobre trading/cripto, redirecione educadamente.
8. Máximo ~300 palavras para FREE, ~500 para VIP.

{signals_ctx}

---
BASE DE CONHECIMENTO DO SIDERADOG:
{kb}
---
"""
    return system


async def ask_agent(
    question: str,
    user_memory: dict,
    recent_signals: list,
    is_vip: bool,
) -> str:
    """Envia pergunta ao agente e retorna resposta."""
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "⚠️ Agente temporariamente indisponível. Tente novamente mais tarde."

    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=api_key)

        model = "claude-sonnet-4-6" if is_vip else "claude-haiku-4-5-20251001"
        system_prompt = _build_system_prompt(user_memory, recent_signals, is_vip)

        response = await client.messages.create(
            model=model,
            max_tokens=600 if is_vip else 350,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )

        text = response.content[0].text.strip()

        # Garante disclaimer ao final
        if "⚠️" not in text and "recomendação" not in text.lower():
            text += "\n\n⚠️ Não é recomendação de investimento."

        return text

    except Exception as e:
        logger.error(f"Erro no agente: {e}")
        return "⚠️ Agente temporariamente indisponível. Tente novamente em alguns minutos."


def reload_knowledge_base():
    """Força o reload da knowledge base (útil após atualização)."""
    global _KNOWLEDGE_BASE
    _KNOWLEDGE_BASE = None
    _load_knowledge_base()
    logger.info("Knowledge base recarregada.")
