"""
Utilitario para descobrir o TELEGRAM_CHANNEL_ID do seu grupo/canal.

Como usar:
  1. Adicione o bot ao seu grupo/canal e torne-o ADMINISTRADOR
  2. Envie qualquer mensagem no grupo (ex: "teste")
  3. Execute: python tools/get_chat_id.py
  4. Copie o chat_id exibido e coloque no .env como TELEGRAM_CHANNEL_ID
"""

import asyncio
import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


async def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN não encontrado no .env")
        return

    bot = Bot(token=token)

    me = await bot.get_me()
    print(f"✅ Bot conectado: @{me.username}")
    print("\n📡 Buscando atualizações recentes...\n")

    updates = await bot.get_updates(limit=20)

    if not updates:
        print("⚠️  Nenhuma mensagem encontrada.")
        print("   → Envie uma mensagem no grupo e execute novamente.")
        return

    chats_seen = set()
    for update in updates:
        msg = update.message or update.channel_post
        if msg and msg.chat.id not in chats_seen:
            chats_seen.add(msg.chat.id)
            chat = msg.chat
            print(f"Chat encontrado:")
            print(f"  Nome:  {chat.title or chat.first_name}")
            print(f"  Tipo:  {chat.type}")
            print(f"  ID:    {chat.id}  ← coloque este no .env como TELEGRAM_CHANNEL_ID")
            print()

    if not chats_seen:
        print("⚠️  Nenhum chat encontrado nas atualizações.")
        print("   → Adicione o bot ao grupo, envie uma mensagem e execute novamente.")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
