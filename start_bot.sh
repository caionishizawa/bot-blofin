#!/usr/bin/env bash
# ─── Bot BloFin — Script de inicialização com loop automático ─────────────────
# Mantém o bot sempre rodando. Se crashar, reinicia automaticamente.
# Uso: ./start_bot.sh

set -euo pipefail

# ── Configurações ───────────────────────────────────────────────────────────
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$BOT_DIR/logs"
LOG_FILE="$LOG_DIR/bot.log"
PID_FILE="$BOT_DIR/bot.pid"
RESTART_DELAY=5       # segundos entre restarts
MAX_RESTARTS=0        # 0 = ilimitado
PYTHON_CMD="${PYTHON_CMD:-python3}"

# ── Setup de diretórios ─────────────────────────────────────────────────────
mkdir -p "$LOG_DIR"

# ── Função de log ────────────────────────────────────────────────────────────
log() {
    local level="$1"; shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

# ── Verificar .env ───────────────────────────────────────────────────────────
if [[ ! -f "$BOT_DIR/.env" ]]; then
    log "ERROR" ".env não encontrado em $BOT_DIR. Copie .env.example e configure."
    exit 1
fi

# ── Registrar PID principal ─────────────────────────────────────────────────
echo $$ > "$PID_FILE"

cleanup() {
    log "INFO" "Sinal de parada recebido. Encerrando bot..."
    rm -f "$PID_FILE"
    # Matar processo filho do bot se existir
    if [[ -n "${BOT_PID:-}" ]] && kill -0 "$BOT_PID" 2>/dev/null; then
        kill "$BOT_PID"
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT SIGQUIT

# ── Verificar dependências ───────────────────────────────────────────────────
if ! command -v "$PYTHON_CMD" &>/dev/null; then
    log "ERROR" "Python não encontrado. Instale com: brew install python"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_CMD" --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
log "INFO" "Usando $PYTHON_CMD versão $PYTHON_VERSION"

# ── Loop principal ───────────────────────────────────────────────────────────
RESTART_COUNT=0

log "INFO" "=========================================="
log "INFO" "  Bot BloFin iniciando (loop automático)"
log "INFO" "  Diretório: $BOT_DIR"
log "INFO" "  Log: $LOG_FILE"
log "INFO" "=========================================="

cd "$BOT_DIR"

# Instalar/atualizar dependências se necessário
if [[ ! -d "$BOT_DIR/.venv" ]]; then
    log "INFO" "Criando ambiente virtual Python..."
    "$PYTHON_CMD" -m venv "$BOT_DIR/.venv"
fi

VENV_PYTHON="$BOT_DIR/.venv/bin/python"
VENV_PIP="$BOT_DIR/.venv/bin/pip"

log "INFO" "Instalando dependências..."
"$VENV_PIP" install -q -r "$BOT_DIR/requirements.txt" 2>&1 | tail -3 | tee -a "$LOG_FILE"

while true; do
    RESTART_COUNT=$((RESTART_COUNT + 1))

    if [[ $MAX_RESTARTS -gt 0 && $RESTART_COUNT -gt $MAX_RESTARTS ]]; then
        log "ERROR" "Limite de $MAX_RESTARTS restarts atingido. Parando."
        exit 1
    fi

    log "INFO" "Iniciando bot (tentativa #$RESTART_COUNT)..."

    # Rodar o bot com env vars do .env carregadas
    set -o allexport
    # shellcheck source=.env
    source "$BOT_DIR/.env" 2>/dev/null || true
    set +o allexport

    # Exportar PYTHONPATH para encontrar módulos em src/
    export PYTHONPATH="$BOT_DIR/src:${PYTHONPATH:-}"

    "$VENV_PYTHON" "$BOT_DIR/src/bot.py" >> "$LOG_FILE" 2>&1 &
    BOT_PID=$!

    log "INFO" "Bot rodando com PID $BOT_PID"
    echo "$BOT_PID" > "$BOT_DIR/bot_process.pid"

    # Aguardar o processo terminar
    wait "$BOT_PID" || EXIT_CODE=$?
    EXIT_CODE="${EXIT_CODE:-0}"

    if [[ $EXIT_CODE -eq 0 ]]; then
        log "INFO" "Bot encerrado normalmente (exit 0). Reiniciando em ${RESTART_DELAY}s..."
    else
        log "WARN" "Bot crashou com código $EXIT_CODE. Reiniciando em ${RESTART_DELAY}s..."
    fi

    sleep "$RESTART_DELAY"
done
