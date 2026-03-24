"""
Agent Memory — persiste contexto de cada usuário no banco.

Tabela agent_memory:
  telegram_id  TEXT PK
  level        TEXT  (iniciante | intermediario | avancado)
  ask_count_today  INTEGER
  ask_date     TEXT  (data YYYY-MM-DD — reseta o contador diário)
  total_asks   INTEGER
  summary      TEXT  (resumo do que o usuário já aprendeu)
  last_topics  TEXT  (JSON lista dos últimos tópicos)
  updated_at   TEXT
"""

import json
import logging
from datetime import datetime, timezone, date

logger = logging.getLogger(__name__)

FREE_DAILY_LIMIT = 3


async def get_user_memory(backend, telegram_id: str) -> dict:
    """Retorna memória do usuário (cria registro padrão se não existir)."""
    try:
        rows = await backend.fetchall(
            "SELECT * FROM agent_memory WHERE telegram_id=?",
            (str(telegram_id),)
        )
        if rows:
            row = rows[0]
            # Normaliza last_topics para lista
            try:
                row["last_topics"] = json.loads(row.get("last_topics") or "[]")
            except Exception:
                row["last_topics"] = []
            return row
    except Exception as e:
        logger.warning(f"Erro ao buscar memória de {telegram_id}: {e}")

    return {
        "telegram_id": str(telegram_id),
        "level": "iniciante",
        "ask_count_today": 0,
        "ask_date": "",
        "total_asks": 0,
        "summary": "",
        "last_topics": [],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def get_ask_count_today(backend, telegram_id: str) -> int:
    """Retorna quantas perguntas o usuário já fez hoje."""
    mem = await get_user_memory(backend, telegram_id)
    today = date.today().isoformat()
    if mem.get("ask_date") != today:
        return 0
    return int(mem.get("ask_count_today", 0))


async def increment_ask_count(backend, telegram_id: str):
    """Incrementa contador diário de perguntas."""
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    try:
        mem = await get_user_memory(backend, telegram_id)
        if mem.get("ask_date") != today:
            count = 1
        else:
            count = int(mem.get("ask_count_today", 0)) + 1
        total = int(mem.get("total_asks", 0)) + 1

        await backend.execute("""
            INSERT INTO agent_memory (telegram_id, level, ask_count_today, ask_date,
                total_asks, summary, last_topics, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                ask_count_today = ?,
                ask_date        = ?,
                total_asks      = ?,
                updated_at      = ?
        """, (
            str(telegram_id), mem.get("level", "iniciante"), count, today,
            total, mem.get("summary", ""), json.dumps(mem.get("last_topics", [])), now,
            count, today, total, now,
        ))
    except Exception as e:
        logger.warning(f"Erro ao incrementar ask count de {telegram_id}: {e}")


async def update_user_memory(backend, telegram_id: str, question: str, level_hint: str = None):
    """Atualiza tópicos recentes e nível do usuário."""
    today = date.today().isoformat()
    now = datetime.now(timezone.utc).isoformat()
    try:
        mem = await get_user_memory(backend, telegram_id)
        topics = mem.get("last_topics", [])

        # Extrai palavras-chave da pergunta como tópico
        topic = question[:60].strip()
        topics = ([topic] + topics)[:10]  # mantém últimos 10 tópicos

        level = level_hint or mem.get("level", "iniciante")

        await backend.execute("""
            INSERT INTO agent_memory (telegram_id, level, ask_count_today, ask_date,
                total_asks, summary, last_topics, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                level       = ?,
                last_topics = ?,
                updated_at  = ?
        """, (
            str(telegram_id), level,
            mem.get("ask_count_today", 0), mem.get("ask_date", today),
            mem.get("total_asks", 0), mem.get("summary", ""),
            json.dumps(topics), now,
            level, json.dumps(topics), now,
        ))
    except Exception as e:
        logger.warning(f"Erro ao atualizar memória de {telegram_id}: {e}")
