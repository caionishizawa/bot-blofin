#!/usr/bin/env bash
# ─── Bot BloFin — Instalador para macOS (autostart via launchd) ───────────────
# Configura o bot para iniciar automaticamente quando o Mac ligar.
#
# Uso:
#   chmod +x install_mac.sh
#   ./install_mac.sh              # instalar
#   ./install_mac.sh --uninstall  # remover autostart
#   ./install_mac.sh --status     # ver status
#   ./install_mac.sh --logs       # ver logs ao vivo

set -euo pipefail

# ── Configurações ────────────────────────────────────────────────────────────
BOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST_NAME="com.botblofin"
PLIST_SRC="$BOT_DIR/com.botblofin.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$BOT_DIR/logs"

# ── Cores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Verificações ─────────────────────────────────────────────────────────────
check_mac() {
    if [[ "$(uname)" != "Darwin" ]]; then
        error "Este script é apenas para macOS."
    fi
}

check_files() {
    if [[ ! -f "$BOT_DIR/start_bot.sh" ]]; then
        error "start_bot.sh não encontrado em $BOT_DIR"
    fi
    if [[ ! -f "$PLIST_SRC" ]]; then
        error "com.botblofin.plist não encontrado em $BOT_DIR"
    fi
    if [[ ! -f "$BOT_DIR/.env" ]]; then
        warn ".env não encontrado. Copie e configure antes de usar:"
        warn "  cp $BOT_DIR/.env.example $BOT_DIR/.env"
        warn "  nano $BOT_DIR/.env"
        echo
        read -r -p "Continuar mesmo assim? (s/N) " ans
        [[ "${ans,,}" == "s" ]] || exit 0
    fi
}

# ── Instalar ─────────────────────────────────────────────────────────────────
install_autostart() {
    check_mac
    check_files

    info "Instalando autostart do Bot BloFin no Mac..."
    echo

    # Criar diretório de logs
    mkdir -p "$LOG_DIR"

    # Tornar script executável
    chmod +x "$BOT_DIR/start_bot.sh"

    # Substituir placeholder no plist com o caminho real
    sed \
        -e "s|BOT_DIR_PLACEHOLDER|$BOT_DIR|g" \
        -e "s|HOME_DIR_PLACEHOLDER|$HOME|g" \
        "$PLIST_SRC" > "$PLIST_DEST"

    success "Plist instalado em: $PLIST_DEST"

    # Descarregar se já estava carregado (evitar duplicatas)
    launchctl unload "$PLIST_DEST" 2>/dev/null || true

    # Carregar o serviço
    launchctl load "$PLIST_DEST"

    echo
    success "Bot BloFin configurado para iniciar automaticamente!"
    echo
    info "O bot vai:"
    echo "  ✅ Iniciar quando você ligar/logar no Mac"
    echo "  ✅ Reiniciar automaticamente se crashar"
    echo "  ✅ Manter loop contínuo de monitoramento (SL/TP a cada 5min)"
    echo
    info "Comandos úteis:"
    echo "  Ver status:  launchctl list | grep botblofin"
    echo "  Ver logs:    tail -f $LOG_DIR/bot.log"
    echo "  Parar:       launchctl unload $PLIST_DEST"
    echo "  Reiniciar:   launchctl unload $PLIST_DEST && launchctl load $PLIST_DEST"
    echo "  Desinstalar: $BOT_DIR/install_mac.sh --uninstall"
    echo
}

# ── Desinstalar ──────────────────────────────────────────────────────────────
uninstall_autostart() {
    check_mac
    info "Removendo autostart do Bot BloFin..."

    if [[ -f "$PLIST_DEST" ]]; then
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
        rm -f "$PLIST_DEST"
        success "Autostart removido."
    else
        warn "Plist não encontrado em $PLIST_DEST. Nada a remover."
    fi

    # Matar processo se estiver rodando
    if [[ -f "$BOT_DIR/bot.pid" ]]; then
        PID=$(cat "$BOT_DIR/bot.pid")
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            success "Processo do bot (PID $PID) encerrado."
        fi
        rm -f "$BOT_DIR/bot.pid"
    fi
    echo
    info "Bot BloFin não iniciará mais automaticamente."
    info "Para iniciar manualmente: cd $BOT_DIR && ./start_bot.sh"
}

# ── Status ───────────────────────────────────────────────────────────────────
show_status() {
    check_mac
    echo
    info "=== Status do Bot BloFin ==="
    echo

    # Status do launchd
    echo -n "  LaunchAgent: "
    if [[ -f "$PLIST_DEST" ]]; then
        LOADED=$(launchctl list | grep "$PLIST_NAME" || echo "")
        if [[ -n "$LOADED" ]]; then
            success "Carregado e ativo"
            PID_STATUS=$(echo "$LOADED" | awk '{print $1}')
            [[ "$PID_STATUS" != "-" ]] && echo "  PID: $PID_STATUS"
        else
            warn "Plist existe mas não está carregado"
        fi
    else
        echo -e "${RED}Não instalado${NC}"
    fi

    # Status do processo do bot
    echo -n "  Processo do bot: "
    if [[ -f "$BOT_DIR/bot_process.pid" ]]; then
        BOT_PID=$(cat "$BOT_DIR/bot_process.pid")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            success "Rodando (PID $BOT_PID)"
        else
            warn "PID file existe mas processo não está rodando (PID $BOT_PID)"
        fi
    else
        echo -e "${YELLOW}PID file não encontrado${NC}"
    fi

    # Últimas linhas do log
    if [[ -f "$LOG_DIR/bot.log" ]]; then
        echo
        info "=== Últimas 10 linhas do log ==="
        tail -10 "$LOG_DIR/bot.log"
    fi
    echo
}

# ── Logs ao vivo ─────────────────────────────────────────────────────────────
show_logs() {
    LOG_FILE="$LOG_DIR/bot.log"
    if [[ -f "$LOG_FILE" ]]; then
        info "Mostrando logs ao vivo (Ctrl+C para sair)..."
        tail -f "$LOG_FILE"
    else
        warn "Log não encontrado em $LOG_FILE. O bot já iniciou?"
    fi
}

# ── Main ─────────────────────────────────────────────────────────────────────
case "${1:-install}" in
    --uninstall|-u)  uninstall_autostart ;;
    --status|-s)     show_status ;;
    --logs|-l)       show_logs ;;
    install|"")      install_autostart ;;
    *)
        echo "Uso: $0 [install|--uninstall|--status|--logs]"
        exit 1
        ;;
esac
