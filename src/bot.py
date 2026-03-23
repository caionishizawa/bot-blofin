"""
Bot BloFin — Orquestrador principal com integração Telegram completa.

Uso:
    cd src && python bot.py
"""

import asyncio
import logging
import os
import random
from datetime import date, datetime, time, timedelta, timezone

import yaml
from aiohttp import web as aiohttp_web
from dotenv import load_dotenv
from telegram import Bot, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

from modules.chart_generator import create_chart, create_pnl_chart
from modules.llm_analyst import analyze_signal
from modules.performance import PerformanceDB
from modules.scanner import scan_pairs
from modules.tracker import TradeTracker
from utils.blofin_api import BloFinAPI
from utils.formatters import (
    format_signal_message,
    format_stats_message,
    format_trades_list,
    format_update_message,
)

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_PAIRS = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "BNB-USDT",
    "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT",
    "MATIC-USDT", "LTC-USDT", "NEAR-USDT", "OP-USDT", "ARB-USDT",
    "APT-USDT", "TRX-USDT", "ATOM-USDT", "INJ-USDT", "FIL-USDT",
]


def load_config(path: str = "config.yaml") -> dict:
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


class BloFinBot:
    """Orquestrador principal do bot com integração Telegram completa."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.tracker = TradeTracker()
        self.db = PerformanceDB(self.config.get("db_path", "data/trades.db"))
        self.api = BloFinAPI()
        self.running = False

        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "")
        self.ref_link = os.getenv("BLOFIN_REF_LINK", self.config.get("ref_link", ""))
        self.bankroll = float(self.config.get("starting_bankroll", 1000.0))
        self.admin_ids = set(filter(None, os.getenv("ADMIN_IDS", "").split(",")))
        self._today_schedule: list = []
        self._realized_pnl_usd: float = 0.0    # atualizado após cada trade fechar
        self._unrealized_pnl_usd: float = 0.0  # atualizado a cada tick de preço
        self._current_bankroll: float = self.bankroll  # banca em tempo real

        # Swing: terça e quinta, uma vez por dia cada
        self._swing_days = {1, 3}  # Monday=0 … Sunday=6 → terça=1, quinta=3
        self._last_swing_date: str = ""

        self._app: Application | None = None

    # ------------------------------------------------------------------
    # Envio de mensagens
    # ------------------------------------------------------------------

    async def _send(self, text: str, photo=None, chat_id: str = None):
        """Envia mensagem ou foto ao canal configurado."""
        target = chat_id or self.channel_id
        if not target:
            logger.warning("TELEGRAM_CHANNEL_ID não configurado — mensagem ignorada")
            return
        try:
            bot: Bot = self._app.bot
            if photo:
                photo.seek(0)
                # Telegram caption limit: 1024 chars
                caption = text[:1024] if text else ""
                await bot.send_photo(
                    chat_id=target,
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )
                # If full text exceeds caption limit, send remainder as message
                if len(text) > 1024:
                    remainder = text[1024:]
                    await bot.send_message(
                        chat_id=target,
                        text=remainder,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                    )
            else:
                await bot.send_message(
                    chat_id=target,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                )
        except TelegramError as e:
            logger.error(f"Telegram erro ao enviar: {e}")

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 *BloFin Signal Bot* — Online!\n\n"
            "Comandos disponíveis:\n"
            "🔍 /scan — Escanear pares agora\n"
            "📋 /trades — Trades ativos\n"
            "📈 /stats — Performance semanal/mensal/anual\n"
            "📊 /pnl — Gráfico de equity curve\n"
            "🖼 /share — Card de resultado do último trade\n"
            "⏹ /stop — Pausar scans automáticos\n"
            "▶️ /resume — Retomar scans\n\n"
            "📡 *Grupos:*\n"
            "✅ /enable — Ativar sinais neste grupo\n"
            "🚫 /disable — Desativar sinais neste grupo\n"
            "📋 /groups — Listar grupos registrados\n\n"
            "🛠 *Admin:*\n"
            "📝 /newtrade — Criar trade manual\n"
            "📅 /agenda — Ver agenda de scans\n"
            "📢 /broadcast — Enviar mensagem para grupos\n",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_scan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🔍 Escaneando pares...")
        chat_id = str(update.effective_chat.id)
        count = await self._scan_cycle(chat_id=chat_id)
        await msg.edit_text(f"✅ Scan concluído — {count} sinal(is) encontrado(s).")

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        trades = self.tracker.get_all()
        # Injeta unrealized_usd em cada trade dict
        for t, active in zip(trades, self.tracker.active_trades.values()):
            t["unrealized_usd"] = active.unrealized_pnl_usd(self.bankroll)
        text = format_trades_list(
            trades,
            current_bankroll=self._current_bankroll,
            realized_pnl=self._realized_pnl_usd,
            unrealized_pnl=self._unrealized_pnl_usd,
            starting_bankroll=self.bankroll,
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        stats = await self.db.get_stats_multi_period(bankroll=self.bankroll)
        text = format_stats_message(stats, starting_bankroll=self.bankroll)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_pnl(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        trades = await self.db.get_recent_trades(limit=50)
        if not trades:
            await update.message.reply_text("📭 Nenhum trade registrado ainda.")
            return
        buf = create_pnl_chart(trades, self.config)
        await update.message.reply_photo(photo=buf, caption="📊 *Equity Curve — NPK Sinais*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_share(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Gera card de resultado do último trade fechado (ou /share <id>)."""
        from modules.pnl_share import create_pnl_share

        trade_id = ctx.args[0] if ctx.args else None

        if trade_id:
            # Busca trade específico por ID
            all_trades = await self.db.get_all_trades(limit=200)
            trade = next((t for t in all_trades if t.get("id", "").startswith(trade_id)), None)
            if not trade:
                await update.message.reply_text(f"❌ Trade `{trade_id}` não encontrado.", parse_mode=ParseMode.MARKDOWN)
                return
        else:
            recent = await self.db.get_recent_trades(limit=1)
            if not recent:
                await update.message.reply_text("📭 Nenhum trade fechado ainda.")
                return
            trade = recent[0]

        import json as _json
        if isinstance(trade.get("reasons"), str):
            trade["reasons"] = _json.loads(trade["reasons"])

        stats = await self.db.get_stats(days=365, bankroll=self.bankroll)
        buf = create_pnl_share(trade, stats=stats, bankroll=self.bankroll, ref_link=self.ref_link)

        pair = trade.get("pair", "")
        direction = trade.get("direction", "")
        await update.message.reply_photo(
            photo=buf,
            caption=f"📊 *Resultado — {pair} {direction}*",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = False
        await update.message.reply_text("⏹ Scans automáticos pausados.")

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = True
        await update.message.reply_text("▶️ Scans automáticos retomados.")

    async def cmd_enable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Enable signal broadcasting in this chat/group."""
        chat = update.effective_chat
        await self.db.enable_group(str(chat.id), chat.title or chat.first_name or "")
        await update.message.reply_text(
            "✅ Sinais *ativados* neste grupo.\n"
            "Os próximos scans serão enviados aqui.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Sinais habilitados em: {chat.title or chat.id} ({chat.id})")

    async def cmd_disable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Disable signal broadcasting in this chat/group."""
        chat = update.effective_chat
        await self.db.disable_group(str(chat.id))
        await update.message.reply_text(
            "⏹ Sinais *desativados* neste grupo.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Sinais desabilitados em: {chat.title or chat.id} ({chat.id})")

    async def cmd_groups(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """List all registered groups and their status."""
        groups = await self.db.list_groups()
        if not groups:
            await update.message.reply_text("Nenhum grupo registrado ainda.")
            return
        lines = ["📋 *Grupos registrados:*", ""]
        for g in groups:
            status = "✅ ativo" if g["enabled"] else "⏹ inativo"
            lines.append(f"{status} — {g['title'] or 'sem título'}  `{g['chat_id']}`")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    def _is_admin(self, update) -> bool:
        return not self.admin_ids or str(update.effective_user.id) in self.admin_ids

    async def cmd_newtrade(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Cria um trade manual. Uso: /newtrade PAR DIREÇÃO ENTRADA SL TP1 TP2 TP3"""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return

        args = ctx.args
        if not args or len(args) < 7:
            await update.message.reply_text(
                "📝 *Uso:* `/newtrade PAR DIREÇÃO ENTRADA SL TP1 TP2 TP3`\n\n"
                "Exemplo:\n`/newtrade BTC-USDT LONG 50000 49000 51500 53000 55000`",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        try:
            pair      = args[0].upper()
            direction = args[1].upper()
            entry     = float(args[2])
            sl        = float(args[3])
            tp1       = float(args[4])
            tp2       = float(args[5])
            tp3       = float(args[6])
        except (ValueError, IndexError):
            await update.message.reply_text("❌ Valores inválidos. Verifique os números.")
            return

        if direction not in ("LONG", "SHORT"):
            await update.message.reply_text("❌ Direção deve ser LONG ou SHORT.")
            return

        rr = round(abs(tp2 - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
        risk_pct = float(self.config.get("risk_pct_per_trade", 2.0))

        signal = {
            "pair": pair,
            "direction": direction,
            "entry": entry,
            "stop_loss": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "risk_pct": risk_pct,
            "bankroll": self.bankroll,
            "rr_ratio": rr,
            "confidence": 85,
            "score": 8.5,
            "reasons": ["Trade manual do admin"],
            "timeframe": "1H",
            "trade_mode": "manual",
            "candles_df": None,
        }

        msg = await update.message.reply_text("📡 Processando trade manual...")

        trade = self.tracker.add_trade(signal)
        analysis = await analyze_signal(signal, mode="scalp")
        from modules.chart_generator import create_chart
        chart_buf = create_chart(signal, self.config)
        text = format_signal_message(signal, analysis=analysis, ref_link=self.ref_link, mode="manual")
        await self.db.save_trade(trade.to_dict(), bankroll=self.bankroll)

        targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
        if self.channel_id and self.channel_id not in targets:
            targets.append(self.channel_id)

        sent = 0
        for target in targets:
            await self._send(text, photo=chart_buf, chat_id=target)
            sent += 1

        await msg.edit_text(f"✅ Trade manual enviado para {sent} grupo(s).")

    async def cmd_agenda(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Mostra a agenda de scans do dia."""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return

        schedule = self._today_schedule
        if not schedule:
            await update.message.reply_text("📅 Nenhuma agenda gerada ainda. O bot gera ao iniciar.")
            return

        now = datetime.now()
        lines = ["📅 *Agenda de Scans — Hoje*", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
        for t in schedule:
            status = "✅" if t <= now else "⏳"
            lines.append(f"{status} `{t.strftime('%H:%M')}`")
        lines.append("")
        lines.append(f"_Bot está {'▶️ rodando' if self.running else '⏹ pausado'}_")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_broadcast(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Envia mensagem personalizada para todos os grupos. Uso: /broadcast TEXTO"""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return

        if not ctx.args:
            await update.message.reply_text("Uso: `/broadcast sua mensagem aqui`", parse_mode=ParseMode.MARKDOWN)
            return

        text = " ".join(ctx.args)
        targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
        if self.channel_id and self.channel_id not in targets:
            targets.append(self.channel_id)

        sent = 0
        for target in targets:
            await self._send(text, chat_id=target)
            sent += 1

        await update.message.reply_text(f"✅ Mensagem enviada para {sent} grupo(s).")

    async def on_bot_added(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Auto-register group when bot is added as member."""
        result: ChatMemberUpdated = update.my_chat_member
        if not result:
            return
        new_status = result.new_chat_member.status
        chat = result.chat
        if new_status in ("member", "administrator"):
            await self.db.enable_group(str(chat.id), chat.title or "")
            logger.info(f"Bot adicionado ao grupo: {chat.title} ({chat.id}) — sinais habilitados automaticamente")
            try:
                await ctx.bot.send_message(
                    chat_id=chat.id,
                    text=(
                        "👋 *BloFin Signal Bot* ativo neste grupo!\n\n"
                        "Sinais serão enviados automaticamente.\n"
                        "Use /disable para desativar ou /enable para reativar."
                    ),
                    parse_mode=ParseMode.MARKDOWN,
                )
            except TelegramError:
                pass
        elif new_status in ("left", "kicked"):
            await self.db.disable_group(str(chat.id))
            logger.info(f"Bot removido do grupo: {chat.title} ({chat.id}) — sinais desabilitados")

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------

    def _is_swing_day(self) -> bool:
        """True on Tue/Thu, once per day."""
        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        if now.weekday() in self._swing_days and today != self._last_swing_date:
            return True
        return False

    async def _scan_cycle(self, chat_id: str = None) -> int:
        """Escaneia todos os pares e envia sinais ao canal. Retorna nº de sinais."""
        pairs = self.config.get("pairs", DEFAULT_PAIRS)
        min_confidence = self.config.get("min_confidence", 50)

        # Swing day: scan 4H, lower RR threshold, lower leverage
        swing_day = self._is_swing_day()
        if swing_day:
            bar = "4H"
            min_rr, max_rr = 1.5, 3.0
            mode = "swing"
        else:
            bar = self.config.get("timeframe", "1H")
            min_rr = self.config.get("min_rr", 1.5)
            max_rr = self.config.get("max_rr", 4.0)
            mode = "scalp"

        logger.info(f"Escaneando {len(pairs)} pares em {bar} [{mode}]...")
        signals = await scan_pairs(pairs, bar=bar)
        logger.info(f"{len(signals)} sinal(is) bruto(s) encontrado(s)")

        filtered = [
            s for s in signals
            if s.get("rr_ratio", 0) >= min_rr
            and s.get("rr_ratio", 0) <= max_rr
            and s.get("confidence", 0) >= min_confidence
        ]
        logger.info(f"{len(filtered)} sinal(is) após filtro [{mode}]")

        # On swing day, take only the best signal (highest score)
        if swing_day and filtered:
            filtered = sorted(filtered, key=lambda s: s.get("score", 0), reverse=True)[:1]
            self._last_swing_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        risk_pct = float(self.config.get("risk_pct_per_trade", 2.0))
        for signal in filtered:
            signal["trade_mode"] = mode
            signal["risk_pct"]   = risk_pct
            signal["bankroll"]   = self.bankroll

            # Swing: override leverage to 3-5x
            if mode == "swing":
                signal["swing_override_lev"] = 4

            trade = self.tracker.add_trade(signal)
            await self.db.save_trade(trade.to_dict(), bankroll=self.bankroll)
            analysis = await analyze_signal(signal, mode=mode)
            chart_buf = create_chart(signal, self.config)
            msg = format_signal_message(signal, analysis=analysis, ref_link=self.ref_link, mode=mode)

            logger.info(
                f"[{mode.upper()}] {signal['pair']} {signal['direction']} "
                f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')}"
            )

            targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
            if chat_id and chat_id not in targets:
                targets.append(chat_id)
            if not targets and self.channel_id:
                targets = [self.channel_id]

            for target in targets:
                await self._send(msg, photo=chart_buf, chat_id=target)

        return len(filtered)

    async def _update_trades(self):
        """Verifica SL/TP nos trades ativos — uma chamada batch à API a cada 5 min.

        Lógica:
          • Uma única chamada GET /mark-price para todos os pares
          • Se preço não bateu SL nem TP → nada é gravado, nada é enviado
          • Se bateu TP1/TP2/TP3/SL → grava no DB, envia notificação
        """
        if not self.tracker.active_trades:
            return

        # ── Batch: um único request para TODOS os preços ───────────────────
        try:
            all_prices = await self.api.get_all_mark_prices()
        except Exception as e:
            logger.warning(f"Batch mark-price falhou ({e}), tentando individual...")
            all_prices = {}

        events_fired = []

        for pair, trade in list(self.tracker.active_trades.items()):
            try:
                price = all_prices.get(pair)

                # Fallback individual só se o par não veio no batch
                if not price:
                    try:
                        price = await self.api.get_mark_price(pair)
                    except Exception:
                        pass
                if not price:
                    continue

                # Atualiza preço atual em memória (para dashboard)
                trade.current_price = price

                event = trade.check_levels(price)
                if not event:
                    # Preço não atingiu nenhum nível — não grava nada
                    continue

                # ── Evento confirmado: TP ou SL bateu ─────────────────────
                trade_dict = trade.to_dict()
                pnl_usd = round(PerformanceDB.calc_pnl_usd(trade_dict, self.bankroll), 2)
                logger.info(
                    f"[{event}] {pair} @ {price:.4f} | "
                    f"PNL: ${pnl_usd:+.2f} ({trade_dict['pnl_pct']:+.2f}%)"
                )

                msg = format_update_message(pair, event, trade_dict, bankroll=self.bankroll)
                await self._send(msg)
                await self.db.save_trade(trade_dict, bankroll=self.bankroll)

                events_fired.append(event)

                if event in ("SL_HIT", "TP3_HIT"):
                    self.tracker.remove_trade(pair)

            except Exception as e:
                logger.error(f"Erro verificando {pair}: {e}")

        # Atualiza PNL realizado somente se houve evento
        if events_fired:
            try:
                stats = await self.db.get_stats(days=36500, bankroll=self.bankroll)
                self._realized_pnl_usd = stats.get("total_pnl_usd", 0.0)
            except Exception:
                pass

        # Recalcula PNL não realizado com preços mais recentes (em memória)
        self._unrealized_pnl_usd = sum(
            t.unrealized_pnl_usd(self.bankroll)
            for t in self.tracker.active_trades.values()
        )
        self._current_bankroll = round(
            self.bankroll + self._realized_pnl_usd + self._unrealized_pnl_usd, 2
        )
        if self.tracker.active_trades:
            logger.debug(
                f"Trades: {len(self.tracker.active_trades)} ativos | "
                f"Banca: ${self._current_bankroll:.2f} "
                f"(real: ${self._realized_pnl_usd:+.2f} | "
                f"aberto: ${self._unrealized_pnl_usd:+.2f})"
            )

    def _schedule_daily_scans(self) -> list:
        """Gera horários aleatórios de scan para o dia atual.

        Janelas:
          • Manhã  08:00–12:00 → 3-5 scans (pesado)
          • Tarde  12:00–17:00 → 0-2 scans (leve)
          • Noite  17:00–22:00 → 3-5 scans (pesado)
        """
        today = date.today()
        scan_times = []

        windows = [
            (time(8, 0),  time(12, 0), 3, 5),   # manhã  — pesado
            (time(12, 0), time(17, 0), 0, 2),   # tarde  — leve
            (time(17, 0), time(22, 0), 3, 5),   # noite  — pesado
        ]

        for start_t, end_t, min_n, max_n in windows:
            count = random.randint(min_n, max_n)
            start_dt = datetime.combine(today, start_t)
            end_dt   = datetime.combine(today, end_t)
            window_minutes = int((end_dt - start_dt).total_seconds() // 60)
            chosen_minutes = sorted(random.sample(range(window_minutes), min(count, window_minutes)))
            for m in chosen_minutes:
                scan_times.append(start_dt + timedelta(minutes=m))

        scan_times.sort()
        logger.info(
            f"Agenda do dia: {len(scan_times)} scans em "
            + ", ".join(t.strftime("%H:%M") for t in scan_times)
        )
        self._today_schedule = scan_times[:]
        return scan_times

    async def _background_loop(self):
        """Loop de background: scan automático por agenda + atualização de trades."""
        update_interval = self.config.get("update_interval", 60)
        logger.info(f"Background loop iniciado (update trades: {update_interval}s)")

        # Gera agenda para hoje
        scheduled = self._schedule_daily_scans()
        current_day = date.today()

        while True:
            try:
                now = datetime.now()

                # Virada do dia — gera nova agenda
                if now.date() != current_day:
                    current_day = now.date()
                    scheduled = self._schedule_daily_scans()

                if self.running:
                    # Atualiza trades ativos a cada tick
                    await self._update_trades()

                    # Dispara scans cujo horário já passou e ainda não foram executados
                    due = [t for t in scheduled if t <= now]
                    if due:
                        scheduled = [t for t in scheduled if t > now]
                        logger.info(f"Executando {len(due)} scan(s) agendado(s) — próximos: {[t.strftime('%H:%M') for t in scheduled]}")
                        await self._scan_cycle()

            except Exception as e:
                logger.error(f"Erro no ciclo: {e}")

            await asyncio.sleep(update_interval)

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    async def run(self):
        """Inicializa o bot Telegram e o loop de scanning."""
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN não definido no .env")

        await self.db.initialize()
        self.running = True

        # Carrega PNL realizado histórico do DB (persiste entre reinícios)
        try:
            stats = await self.db.get_stats(days=36500, bankroll=self.bankroll)
            self._realized_pnl_usd = stats.get("total_pnl_usd", 0.0)
            self._current_bankroll = round(self.bankroll + self._realized_pnl_usd, 2)
            logger.info(f"PNL histórico: ${self._realized_pnl_usd:+.2f} | Banca: ${self._current_bankroll:.2f}")
        except Exception as e:
            logger.warning(f"Erro ao carregar PNL histórico: {e}")

        # Recarrega trades abertos do DB (não fechados)
        try:
            import json as _json
            open_trades = await self.db.get_open_trades()
            for t in open_trades:
                if isinstance(t.get("reasons"), str):
                    t["reasons"] = _json.loads(t["reasons"])
                self.tracker.add_trade(t)
            if open_trades:
                logger.info(f"{len(open_trades)} trade(s) aberto(s) recarregado(s) do DB")
        except Exception as e:
            logger.warning(f"Erro ao recarregar trades abertos: {e}")

        self._app = Application.builder().token(self.token).build()

        self._app.add_handler(CommandHandler("start", self.cmd_start))
        self._app.add_handler(CommandHandler("scan", self.cmd_scan))
        self._app.add_handler(CommandHandler("trades", self.cmd_trades))
        self._app.add_handler(CommandHandler("stats", self.cmd_stats))
        self._app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self._app.add_handler(CommandHandler("stop", self.cmd_stop))
        self._app.add_handler(CommandHandler("resume", self.cmd_resume))
        self._app.add_handler(CommandHandler("enable", self.cmd_enable))
        self._app.add_handler(CommandHandler("disable", self.cmd_disable))
        self._app.add_handler(CommandHandler("groups", self.cmd_groups))
        self._app.add_handler(CommandHandler("newtrade", self.cmd_newtrade))
        self._app.add_handler(CommandHandler("agenda", self.cmd_agenda))
        self._app.add_handler(CommandHandler("broadcast", self.cmd_broadcast))
        self._app.add_handler(CommandHandler("share", self.cmd_share))
        self._app.add_handler(ChatMemberHandler(self.on_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

        logger.info("Bot iniciando...")

        async with self._app:
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)

            # Dashboard web
            dashboard_port = self.config.get("dashboard_port", 8080)
            from dashboard import create_dashboard
            dash_app = create_dashboard(self)
            dash_runner = aiohttp_web.AppRunner(dash_app)
            await dash_runner.setup()
            dash_site = aiohttp_web.TCPSite(dash_runner, "0.0.0.0", dashboard_port)
            await dash_site.start()
            logger.info(f"Dashboard rodando em http://localhost:{dashboard_port}")

            bg_task = asyncio.create_task(self._background_loop())
            logger.info("Bot rodando. Pressione Ctrl+C para parar.")

            try:
                while True:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                bg_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                await dash_runner.cleanup()
                await self._app.updater.stop()
                await self._app.stop()
                await self.api.close()
                await self.db.close()
                logger.info("Bot encerrado.")


def main():
    config = load_config()
    bot = BloFinBot(config)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
