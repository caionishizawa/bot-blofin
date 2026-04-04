#!/bin/bash
# Wrapper para manter o Mac acordado e o bot sempre rodando

LOG="/Users/sideradog/bot-blofin/bot.log"
PYTHON="/opt/homebrew/bin/python3.11"
BOT="/Users/sideradog/bot-blofin/src/bot.py"
WORKDIR="/Users/sideradog/bot-blofin/src"

# Evita que o Mac durma enquanto o bot roda
caffeinate -s &
CAFF_PID=$!
echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] caffeinate PID $CAFF_PID — Mac não vai dormir" >> "$LOG"

# Aguarda rede ficar disponível (até 60s)
MAX_WAIT=60
WAITED=0
until curl -s --max-time 5 https://api.telegram.org > /dev/null 2>&1; do
    echo "$(date '+%Y-%m-%d %H:%M:%S') [INFO] Aguardando rede... ($WAITED/$MAX_WAIT s)" >> "$LOG"
    sleep 5
    WAITED=$((WAITED + 5))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') [WARN] Rede indisponível após ${MAX_WAIT}s, tentando mesmo assim..." >> "$LOG"
        break
    fi
done

# Inicia o bot
cd "$WORKDIR" && exec "$PYTHON" "$BOT"

# Limpa caffeinate se o bot sair
kill $CAFF_PID 2>/dev/null
