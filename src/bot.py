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
from typing import Optional

import yaml
from aiohttp import web as aiohttp_web
from dotenv import load_dotenv
from telegram import Bot, ChatMemberUpdated, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, ChatMemberHandler, CommandHandler, ContextTypes

from modules.chart_generator import create_chart, create_pnl_chart
from modules.llm_analyst import analyze_signal, fetch_fear_greed
from modules.performance import PerformanceDB
from modules.position_sizer import calculate_risk_pct
from modules.scanner import scan_pairs
from modules.tracker import TradeTracker
from utils.blofin_api import BloFinAPI
from utils.formatters import (
    format_portfolio_header,
    format_signal_message,
    format_stats_message,
    format_trades_list,
    format_update_message,
    format_weekly_recap,
    format_weekly_macro,
)
from agent.agent import ask_agent, reload_knowledge_base
from agent.memory import (
    get_user_memory,
    get_ask_count_today,
    increment_ask_count,
    update_user_memory,
    FREE_DAILY_LIMIT,
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
        self.free_channel_id  = os.getenv("TELEGRAM_FREE_CHANNEL_ID", self.channel_id)
        self.vip_channel_id   = os.getenv("TELEGRAM_VIP_CHANNEL_ID",  self.channel_id)
        self.admin_id         = os.getenv("TELEGRAM_ADMIN_ID", "")
        self._last_signal_at: Optional[datetime] = None
        self.ref_link  = os.getenv("BLOFIN_REF_LINK", self.config.get("ref_link", ""))
        self.calc_link  = os.getenv("CALCULATOR_LINK", "")
        self.thread_id  = int(os.getenv("TELEGRAM_THREAD_ID", "0")) or None
        self.bankroll = float(self.config.get("starting_bankroll", 1000.0))
        self.admin_ids = set(filter(None, os.getenv("ADMIN_IDS", "").split(",")))
        self._today_schedule: list = []
        self._realized_pnl_usd: float = 0.0    # atualizado após cada trade fechar
        self._unrealized_pnl_usd: float = 0.0  # atualizado a cada tick de preço
        self._current_bankroll: float = self.bankroll  # banca em tempo real

        # Fila de sinais do portfolio agendados para envio ao longo do dia
        # Cada item: {send_at: datetime, signal: dict, llm_mode: str}
        self._pending_signals: list = []

        # Garante que o portfolio só roda UMA vez por dia, mesmo com restart/redeploy
        self._portfolio_sent_date: str = ""

        # Mensagem de bom dia — enviada uma vez por dia às 08:00 BRT (11:00 UTC)
        self._morning_sent_date: str = ""

        # Swing: terça e quinta, uma vez por dia cada
        self._swing_days = {1, 3}  # Monday=0 … Sunday=6 → terça=1, quinta=3
        self._last_swing_date: str = ""

        # VIP IDs (podem ser atualizados pelo admin via /addvip)
        self._vip_ids: set = set(filter(None, os.getenv("VIP_IDS", "").split(",")))

        # Modo mentor (conversa livre VIP) — telegram_id: bool
        self._mentor_sessions: dict[str, bool] = {}

        self._app: Application | None = None

        # Payment Manager — inicializado após self.db.initialize()
        # O bot_app é injetado no run() após self._app ser criado
        from modules.payment import PaymentManager
        self.payment_manager = PaymentManager(db=self.db)

    # ------------------------------------------------------------------
    # Envio de mensagens
    # ------------------------------------------------------------------

    async def _send(self, text: str, photo=None, chat_id: str = None):
        """Envia mensagem SEMPRE no tópico BOT IA (thread_id obrigatório).
        NUNCA envia no general — bloqueia se TELEGRAM_THREAD_ID não estiver configurado."""
        target = self.free_channel_id
        if not target:
            logger.error("TELEGRAM_FREE_CHANNEL_ID não configurado — mensagem bloqueada")
            return
        thread = self.thread_id
        if not thread:
            logger.error("TELEGRAM_THREAD_ID não configurado — mensagem bloqueada para evitar envio no general")
            return
        try:
            bot: Bot = self._app.bot
            if photo:
                photo.seek(0)
                caption = text[:1024] if text else ""
                await bot.send_photo(
                    chat_id=target,
                    photo=photo,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                    message_thread_id=thread,
                )
                if len(text) > 1024:
                    remainder = text[1024:]
                    await bot.send_message(
                        chat_id=target,
                        text=remainder,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                        message_thread_id=thread,
                    )
            else:
                await bot.send_message(
                    chat_id=target,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True,
                    message_thread_id=thread,
                )
        except TelegramError as e:
            logger.error(f"Telegram erro ao enviar: {e}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_thread(self, update) -> Optional[int]:
        """Retorna thread_id se o comando foi enviado no canal principal."""
        if update and update.effective_chat:
            cid = str(update.effective_chat.id)
            if cid in (self.channel_id, self.free_channel_id):
                return self.thread_id
        return None

    async def _reply(self, update, text: str, parse_mode=None, **kwargs):
        """reply_text forçando thread_id quando no canal principal."""
        return await update.message.reply_text(
            text,
            parse_mode=parse_mode,
            message_thread_id=self._get_thread(update),
            **kwargs,
        )

    async def _reply_photo(self, update, photo, caption: str = "", parse_mode=None, **kwargs):
        """reply_photo forçando thread_id quando no canal principal."""
        return await update.message.reply_photo(
            photo=photo,
            caption=caption,
            parse_mode=parse_mode,
            message_thread_id=self._get_thread(update),
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Comandos
    # ------------------------------------------------------------------

    async def cmd_start(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await self._reply(update, 
            "👋 *SidQuant Bot* — Online!\n\n"
            "📡 *Sinais:*\n"
            "🔍 /scan — Escanear pares agora\n"
            "📋 /trades — Trades ativos\n"
            "📈 /stats — Performance semanal/mensal/anual\n"
            "🎯 /performance — Breakdown por estilo (scalp/daytrade/swing)\n"
            "📊 /pnl — Gráfico de equity curve\n"
            "🖼 /share — Card de resultado do último trade\n"
            "⏹ /stop — Pausar scans automáticos\n"
            "▶️ /resume — Retomar scans\n\n"
            "🤖 *Agente Educacional:*\n"
            "❓ /ask pergunta — Tirar dúvidas de trading (FREE: 3/dia)\n"
            "🧑‍🏫 /mentor — Modo conversa livre (VIP)\n\n"
            "📡 *Grupos:*\n"
            "✅ /enable — Ativar sinais neste grupo\n"
            "🚫 /disable — Desativar sinais neste grupo\n"
            "📋 /groups — Listar grupos registrados\n\n"
            "🛠 *Admin:*\n"
            "📝 /newtrade — Criar trade manual\n"
            "📅 /agenda — Ver agenda de scans\n"
            "📢 /broadcast — Enviar mensagem para grupos\n"
            "👑 /addvip — Liberar acesso VIP a usuário\n"
            "🔄 /reloadkb — Recarregar base de conhecimento\n",
            parse_mode=ParseMode.MARKDOWN,
            message_thread_id=self._get_thread(update),
        )

    async def cmd_scan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        msg = await self._reply(update, "🔍 Escaneando pares...")
        count = await self._scan_cycle()
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
        await self._reply(update, text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        stats = await self.db.get_stats_multi_period(bankroll=self.bankroll)
        text = format_stats_message(stats, starting_bankroll=self.bankroll)
        await self._reply(update, text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_performance(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Breakdown de performance por estilo (scalp / daytrade / swing)."""
        by_style = await self.db.get_stats_by_style(days=30, bankroll=self.bankroll)
        style_icons = {"scalp": "⚡", "daytrade": "📊", "swing": "📈"}
        style_labels = {"scalp": "SCALP (15m/30m)", "daytrade": "DAY TRADE (1H/2H)", "swing": "SWING (4H/1D)"}
        lines = ["📊 *Performance por Estilo — últimos 30d*", "━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]
        best_style = None
        best_pnl   = None
        for style in ("scalp", "daytrade", "swing"):
            d = by_style.get(style, {})
            if not d.get("trades"):
                lines.append(f"{style_icons[style]} *{style_labels[style]}*\n  _Sem trades no período_\n")
                continue
            pnl_str = f"+${d['total_pnl_usd']:.2f}" if d["total_pnl_usd"] >= 0 else f"-${abs(d['total_pnl_usd']):.2f}"
            avg_str = f"+${d['avg_pnl_usd']:.2f}" if d["avg_pnl_usd"] >= 0 else f"-${abs(d['avg_pnl_usd']):.2f}"
            lines.append(
                f"{style_icons[style]} *{style_labels[style]}*\n"
                f"  Trades: `{d['trades']}` · WR: `{d['win_rate']}%`\n"
                f"  Total: `{pnl_str}` · Avg/trade: `{avg_str}`\n"
            )
            if best_pnl is None or d["avg_pnl_usd"] > best_pnl:
                best_pnl   = d["avg_pnl_usd"]
                best_style = style_labels[style]
        if best_style:
            lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"🏆 _Melhor avg/trade: *{best_style}*_")
        await self._reply(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_pnl(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        trades = await self.db.get_recent_trades(limit=50)
        if not trades:
            await self._reply(update, "📭 Nenhum trade registrado ainda.")
            return
        buf = create_pnl_chart(trades, self.config)
        await self._reply_photo(update, buf, caption="📊 *Equity Curve — NPK Sinais*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_share(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Gera card de resultado do último trade fechado (ou /share <id>)."""
        from modules.pnl_share import create_pnl_share

        trade_id = ctx.args[0] if ctx.args else None

        if trade_id:
            # Busca trade específico por ID
            all_trades = await self.db.get_all_trades(limit=200)
            trade = next((t for t in all_trades if t.get("id", "").startswith(trade_id)), None)
            if not trade:
                await self._reply(update, f"❌ Trade `{trade_id}` não encontrado.", parse_mode=ParseMode.MARKDOWN)
                return
        else:
            recent = await self.db.get_recent_trades(limit=1)
            if not recent:
                await self._reply(update, "📭 Nenhum trade fechado ainda.")
                return
            trade = recent[0]

        import json as _json
        if isinstance(trade.get("reasons"), str):
            trade["reasons"] = _json.loads(trade["reasons"])

        stats = await self.db.get_stats(days=365, bankroll=self.bankroll)
        buf = create_pnl_share(trade, stats=stats, bankroll=self.bankroll, ref_link=self.ref_link)

        pair = trade.get("pair", "")
        direction = trade.get("direction", "")
        await self._reply_photo(update, buf, caption=f"📊 *Resultado — {pair} {direction}*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = False
        await self._reply(update, "⏹ Scans automáticos pausados.")

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = True
        await self._reply(update, "▶️ Scans automáticos retomados.")

    async def cmd_enable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Enable signal broadcasting in this chat/group."""
        chat = update.effective_chat
        await self.db.enable_group(str(chat.id), chat.title or chat.first_name or "")
        await self._reply(update, 
            "✅ Sinais *ativados* neste grupo.\n"
            "Os próximos scans serão enviados aqui.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Sinais habilitados em: {chat.title or chat.id} ({chat.id})")

    async def cmd_disable(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Disable signal broadcasting in this chat/group."""
        chat = update.effective_chat
        await self.db.disable_group(str(chat.id))
        await self._reply(update, 
            "⏹ Sinais *desativados* neste grupo.",
            parse_mode=ParseMode.MARKDOWN,
        )
        logger.info(f"Sinais desabilitados em: {chat.title or chat.id} ({chat.id})")

    async def cmd_groups(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """List all registered groups and their status."""
        groups = await self.db.list_groups()
        if not groups:
            await self._reply(update, "Nenhum grupo registrado ainda.")
            return
        lines = ["📋 *Grupos registrados:*", ""]
        for g in groups:
            status = "✅ ativo" if g["enabled"] else "⏹ inativo"
            lines.append(f"{status} — {g['title'] or 'sem título'}  `{g['chat_id']}`")
        await self._reply(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    def _is_admin(self, update) -> bool:
        if not self.admin_ids:
            return False  # bloqueia tudo se ADMIN_IDS não estiver configurado
        return str(update.effective_user.id) in self.admin_ids

    async def cmd_cleartrades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: limpa todos os trades ativos do tracker. Uso: /cleartrades"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        count = len(self.tracker.active_trades)
        self.tracker.active_trades.clear()
        await self._reply(update, f"✅ {count} trade(s) removido(s) do tracker.")

    async def cmd_resetall(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: zera todo o histórico de trades e PnL. Uso: /resetall"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        # Limpa tracker em memória
        trade_count = len(self.tracker.active_trades)
        self.tracker.active_trades.clear()
        # Limpa banco de dados
        await self.db.reset_trades()
        # Zera contadores de PnL
        self._realized_pnl_usd = 0.0
        self._unrealized_pnl_usd = 0.0
        self._current_bankroll = self.bankroll
        # Reseta flag do portfolio
        self._portfolio_sent_date = ""
        logger.info("Reset completo: trades, PnL e banca zerados.")
        await self._reply(
            update,
            f"🔄 *Reset completo!*\n\n"
            f"• {trade_count} trade(s) ativos removidos\n"
            f"• Histórico do DB apagado\n"
            f"• PnL zerado → $0.00\n"
            f"• Banca → ${self.bankroll:.2f}\n\n"
            f"_Começando do zero agora_ ✅",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_forcescan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: força um scan imediato e envia sinal. Uso: /forcescan [1H|4H|15m]"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        args = ctx.args
        bar = args[0].upper() if args else "1H"
        mode = "scalp" if bar in ("15m", "30m", "1H") else "swing"
        msg = await self._reply(update, f"🔍 Forçando scan {bar}...")
        mission = {"bar": bar, "mode": mode, "max_signals": 1}
        count = await self._scan_cycle(mission=mission)
        if count:
            await msg.edit_text(f"✅ {count} sinal(is) enviado(s) — {bar}")
        else:
            await msg.edit_text(f"⚠️ Nenhum sinal válido encontrado no {bar}. Tente outro timeframe.")

    async def cmd_signal(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: força sinal num par específico. Uso: /signal PAR [TIMEFRAME]
        Exemplo: /signal HYPE-USDT 4H
        Gera o trade com níveis baseados em ATR + indicadores e envia com gráfico + análise."""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        args = ctx.args
        if not args:
            await self._reply(update, "📝 Uso: `/signal PAR [TIMEFRAME]`\nEx: `/signal HYPE-USDT 4H`",
                              parse_mode=ParseMode.MARKDOWN)
            return

        pair = args[0].upper()
        bar  = args[1].upper() if len(args) > 1 else "4H"
        mode = "scalp" if bar in ("15m", "30m", "1H") else "swing"

        msg = await self._reply(update, f"🔍 Analisando {pair} {bar}...")

        try:
            from utils.indicators import candles_to_df, add_all_indicators, detect_signal
            from utils.blofin_api import BloFinAPI as _API
            from modules.position_sizer import calculate_risk_pct

            candles = await self.api.get_candles(pair, bar=bar, limit=100)
            if not candles:
                await msg.edit_text(f"⚠️ Par {pair} não encontrado na BloFin.")
                return

            df = candles_to_df(candles)
            df = add_all_indicators(df)

            # Tenta sinal automático primeiro
            scalp = bar in ("15m", "30m", "1H")
            signal = detect_signal(df, scalp=scalp, bar=bar)

            # Se não detectou, monta sinal manual com ATR
            if not signal:
                c     = df.iloc[-1]
                price = float(c["close"])
                atr   = float(c["atr"])
                rsi   = float(c["rsi"])
                ema9  = float(c["ema9"])
                ema21 = float(c["ema21"])
                macd_hist = float(c["macd_hist"])

                # Viés: MACD hist positivo OU RSI < 50 e acima EMA9 → LONG
                direction = "LONG" if (macd_hist > 0 or (rsi < 50 and price >= ema9)) else "SHORT"

                # TPs calibrados para RR ponderado ~2.3
                # splits 35/45/20 → 0.35*1.5R + 0.45*2.3R + 0.20*3.5R = 2.26 ≈ 2.3
                risk = round(1.5 * atr, 4)
                if direction == "LONG":
                    entry = round(price, 4)
                    sl    = round(price - risk, 4)
                    tp1   = round(price + 1.5 * atr, 4)
                    tp2   = round(price + 2.3 * atr, 4)
                    tp3   = round(price + 3.5 * atr, 4)
                else:
                    entry = round(price, 4)
                    sl    = round(price + risk, 4)
                    tp1   = round(price - 1.5 * atr, 4)
                    tp2   = round(price - 2.3 * atr, 4)
                    tp3   = round(price - 3.5 * atr, 4)

                signal = {
                    "pair":       pair,
                    "direction":  direction,
                    "entry":      entry,
                    "stop_loss":  sl,
                    "tp1":        tp1,
                    "tp2":        tp2,
                    "tp3":        tp3,
                    "rr_ratio":   2.3,
                    "confidence": 62,
                    "score":      6.2,
                    "bar":        bar,
                    "tp_count":   3,
                    "reasons":    [f"RSI {rsi:.0f}", f"MACD hist {macd_hist:+.3f}",
                                   f"EMA9 {ema9:.2f}", f"ATR {atr:.3f}"],
                }
            else:
                signal["pair"] = pair

            # Sizing e metadados
            try:
                sizing_stats = await self.db.get_sizing_stats(bankroll=self.bankroll)
            except Exception:
                sizing_stats = {}
            risk_pct, sizing_reason = calculate_risk_pct(signal, sizing_stats)
            signal["risk_pct"]    = risk_pct
            signal["sizing_info"] = sizing_reason
            signal["bankroll"]    = self.bankroll
            signal["trade_style"] = mode
            signal["trade_mode"]  = mode
            signal["setup_type"]  = self._classify_setup(signal, mode)
            signal["calc_link"]   = self.calc_link

            # Envia com gráfico + análise LLM
            await self._register_trade(signal)
            analysis  = await analyze_signal(signal, mode=mode)
            chart_buf = create_chart(signal, self.config)
            text      = format_signal_message(signal, analysis=analysis,
                                              ref_link=self.ref_link, mode=mode)

            await self._send(text, photo=chart_buf)
            self._last_signal_at = datetime.now(timezone.utc)
            await msg.edit_text(f"✅ Sinal {pair} {bar} enviado!")

        except Exception as e:
            logger.error(f"Erro em /signal {pair} {bar}: {e}")
            await msg.edit_text(f"❌ Erro ao gerar sinal: {e}")

    async def cmd_newtrade(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Cria um trade manual. Uso: /newtrade PAR DIREÇÃO ENTRADA SL TP1 TP2 TP3"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return

        args = ctx.args
        if not args or len(args) < 7:
            await self._reply(update, 
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
            await self._reply(update, "❌ Valores inválidos. Verifique os números.")
            return

        if direction not in ("LONG", "SHORT"):
            await self._reply(update, "❌ Direção deve ser LONG ou SHORT.")
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

        msg = await self._reply(update, "📡 Processando trade manual...")

        await self._register_trade(signal)
        analysis = await analyze_signal(signal, mode="scalp")
        from modules.chart_generator import create_chart
        chart_buf = create_chart(signal, self.config)
        text = format_signal_message(signal, analysis=analysis, ref_link=self.ref_link, mode="manual")
        await self._send(text, photo=chart_buf)
        await msg.edit_text("✅ Trade manual enviado para BOT IA.")

    async def cmd_agenda(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Mostra a agenda de scans do dia."""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return

        schedule = self._today_schedule
        if not schedule:
            await self._reply(update, "📅 Nenhuma agenda gerada ainda. O bot gera ao iniciar.")
            return

        now = datetime.now()
        lines = ["📅 *Agenda de Scans — Hoje*", "┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄"]
        for t in schedule:
            status = "✅" if t <= now else "⏳"
            lines.append(f"{status} `{t.strftime('%H:%M')}`  _BRT_")
        lines.append("")
        lines.append(f"_Bot está {'▶️ rodando' if self.running else '⏹ pausado'}_")
        await self._reply(update, "\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_macro(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Dispara manualmente a análise macro semanal."""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        msg = await self._reply(update, "📊 Gerando análise macro semanal...")
        await self._send_weekly_macro()
        await msg.edit_text("✅ Análise macro enviada.")

    async def cmd_broadcast(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Envia mensagem personalizada para todos os grupos. Uso: /broadcast TEXTO"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return

        if not ctx.args:
            await self._reply(update, "Uso: `/broadcast sua mensagem aqui`", parse_mode=ParseMode.MARKDOWN)
            return

        text = " ".join(ctx.args)
        await self._send(text)
        await self._reply(update, "✅ Mensagem enviada para BOT IA.")

    # ------------------------------------------------------------------
    # Agente Educacional — /ask e /mentor
    # ------------------------------------------------------------------

    def _is_vip(self, telegram_id: str) -> bool:
        """Verificação síncrona rápida (apenas memória). Use _is_vip_async para checar o banco."""
        return str(telegram_id) in self._vip_ids or str(telegram_id) in self.admin_ids

    async def _is_vip_async(self, telegram_id: str) -> bool:
        """
        Verificação completa de acesso VIP:
        1. admin ou VIP_IDS env var → acesso imediato
        2. subscribers table no banco → assinatura ativa e não expirada
        """
        if self._is_vip(telegram_id):
            return True
        try:
            return await self.db.is_vip_subscriber(str(telegram_id))
        except Exception:
            return False

    async def cmd_minhaconta(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Usuário consulta seu status de assinatura VIP."""
        user_id = str(update.effective_user.id)
        is_vip = await self._is_vip_async(user_id)

        if self._is_vip(user_id):
            # Admin ou VIP_IDS env var
            msg = (
                "👑 *Conta: Admin / VIP Manual*\n\n"
                "Você tem acesso VIP permanente configurado diretamente no servidor.\n"
                "Todos os recursos estão disponíveis sem prazo de validade."
            )
            await self._reply(update, msg, parse_mode=ParseMode.MARKDOWN)
            return

        if is_vip:
            sub = await self.db.get_subscriber(user_id)
            expires = sub.get("expires_at", "")[:10] if sub else "—"
            plan = sub.get("plan", "monthly")
            platform = sub.get("platform", "—")
            plan_display = "Mensal" if plan == "monthly" else "Anual"
            platform_display = {
                "hotmart": "Hotmart", "stripe": "Stripe",
                "mercadopago": "Mercado Pago", "manual": "Admin",
            }.get(platform, platform.capitalize())

            msg = (
                f"⭐ *Conta VIP ativa*\n\n"
                f"📦 Plano: *{plan_display}*\n"
                f"💳 Plataforma: {platform_display}\n"
                f"📅 Validade: `{expires}`\n\n"
                f"Você tem acesso a todos os recursos VIP:\n"
                f"• Sinais completos com Entry, SL e TP\n"
                f"• Análise de IA completa\n"
                f"• Chat ilimitado com o agente\n\n"
                f"_Use /ask para perguntar ao agente educacional._"
            )
        else:
            ref = self.ref_link or "https://partner.blofin.com/d/sideradog"
            msg = (
                "🆓 *Conta FREE*\n\n"
                "Você tem acesso ao plano gratuito.\n\n"
                "Com o VIP você recebe:\n"
                "• Sinais completos *antes* do trade (Entry + SL + TP1/2/3)\n"
                "• Análise de IA detalhada em PT-BR\n"
                "• Chat ilimitado com o agente educacional\n"
                "• Dashboard pessoal de performance\n\n"
                f"👉 *Assinar VIP*: {ref}"
            )

        await self._reply(update, msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_ask(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Responde dúvida de trading. FREE: 3/dia | VIP: ilimitado."""
        user_id = str(update.effective_user.id)
        question = " ".join(ctx.args) if ctx.args else ""

        if not question:
            await self._reply(update, 
                "🤖 *SidAgent* — Agente educacional do sideradog\n\n"
                "Use: `/ask sua pergunta aqui`\n\n"
                "Exemplos:\n"
                "• `/ask Como valido uma entrada com confluência?`\n"
                "• `/ask O que é RSI e como uso?`\n"
                "• `/ask Qual tamanho de posição para iniciante?`\n\n"
                f"_FREE: {FREE_DAILY_LIMIT} perguntas/dia | VIP: ilimitado_",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        is_vip = await self._is_vip_async(user_id)

        # Checa limite diário para FREE
        if not is_vip:
            count_today = await get_ask_count_today(self.db._backend, user_id)
            if count_today >= FREE_DAILY_LIMIT:
                await self._reply(update, 
                    f"⏳ Você atingiu o limite de *{FREE_DAILY_LIMIT} perguntas/dia* no plano FREE.\n\n"
                    f"Quer respostas ilimitadas + mais detalhadas?\n"
                    f"👉 Acesse o VIP: {self.ref_link or 'https://partner.blofin.com/d/sideradog'}",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        # Feedback de carregamento
        msg = await self._reply(update, "🤖 Pensando...")

        # Coleta contexto
        user_memory = await get_user_memory(self.db._backend, user_id)
        recent_signals = self.tracker.get_all()

        # Chama o agente
        response = await ask_agent(
            question=question,
            user_memory=user_memory,
            recent_signals=recent_signals,
            is_vip=is_vip,
        )

        # Atualiza memória e contador
        await increment_ask_count(self.db._backend, user_id)
        await update_user_memory(self.db._backend, user_id, question)

        # Envia resposta
        tier_badge = "⭐ VIP" if is_vip else "🆓 FREE"
        header = f"🤖 *SidAgent* [{tier_badge}]\n\n"
        await msg.edit_text(
            header + response,
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_mentor(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Modo mentor VIP — conversa livre com o agente."""
        user_id = str(update.effective_user.id)

        if not await self._is_vip_async(user_id):
            await self._reply(update, 
                "⭐ O modo `/mentor` é exclusivo para assinantes *VIP*.\n\n"
                f"👉 Acesse o VIP: {self.ref_link or 'https://partner.blofin.com/d/sideradog'}\n\n"
                "No plano FREE, use `/ask sua pergunta` para até 3 perguntas/dia.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await self._reply(update, 
            "🧑‍🏫 *Modo Mentor Ativo* ⭐\n\n"
            "Me faz qualquer pergunta sobre trading, setups, gestão de risco, "
            "psicologia ou os sinais do bot.\n\n"
            "Use `/ask sua pergunta` para conversar.\n\n"
            "_VIP: sem limite de perguntas, respostas mais detalhadas (Claude Sonnet)._",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_reloadkb(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: recarrega a knowledge base do agente sem reiniciar o bot."""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        reload_knowledge_base()
        await self._reply(update, "✅ Knowledge base recarregada com sucesso.")

    async def cmd_addvip(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: adiciona usuário à lista VIP em memória. Uso: /addvip <telegram_id>"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        if not ctx.args:
            await self._reply(update, "Uso: `/addvip <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
            return
        vip_id = ctx.args[0].strip()
        self._vip_ids.add(vip_id)
        await self._reply(update, f"✅ Usuário `{vip_id}` adicionado ao VIP.", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"VIP adicionado: {vip_id}")

    async def cmd_removevip(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: remove usuário do VIP. Uso: /removevip <telegram_id>"""
        if not self._is_admin(update):
            await self._reply(update, "⛔ Acesso restrito.")
            return
        if not ctx.args:
            await self._reply(update, "Uso: `/removevip <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
            return
        vip_id = ctx.args[0].strip()
        self._vip_ids.discard(vip_id)
        await self._reply(update, f"✅ Usuário `{vip_id}` removido do VIP.", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"VIP removido: {vip_id}")

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

    async def _send_morning_message(self):
        """Envia mensagem de bom dia às 08:00 BRT com preço real do BTC."""
        try:
            # Busca preço e variação do BTC
            candles = await self.api.get_candles("BTC-USDT", bar="1H", limit=2)
            btc_price = 0.0
            btc_change = 0.0
            if candles and len(candles) >= 2:
                from utils.indicators import candles_to_df
                df = candles_to_df(candles)
                btc_price  = float(df.iloc[-1]["close"])
                btc_change = round((df.iloc[-1]["close"] - df.iloc[-2]["close"]) / df.iloc[-2]["close"] * 100, 2)

            price_str  = f"${btc_price:,.0f}" if btc_price else "carregando..."
            change_str = f"{btc_change:+.2f}%" if btc_price else ""
            trend_str  = "lateral" if abs(btc_change) < 0.5 else ("com viés de alta" if btc_change > 0 else "com viés de baixa")

            weekday_names = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
            weekday = weekday_names[datetime.now().weekday()]

            msg = (
                f"⚡ Bom dia — @sideradogcripto\n\n"
                f"Iniciando o scan de hoje. BTC em {price_str} ({change_str}) — mercado {trend_str}.\n\n"
                f"Hoje o bot vai selecionar as melhores oportunidades e mandar ao longo do dia.\n"
                f"Fique atento."
            )

            await self._send(msg)
            logger.info(f"Mensagem de bom dia enviada — BTC {price_str}")

        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de bom dia: {e}")

    async def _send_weekly_macro(self, weekday_name: str = "Segunda-feira"):
        """Coleta dados de mercado + Fear&Greed, gera análise macro e entradas de convicção."""
        from modules.llm_analyst import analyze_weekly_macro

        logger.info("Gerando análise macro semanal...")
        try:
            # ── Coleta dados de mercado (4H para contexto) ──────────────────
            macro_pairs = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
            market_raw  = {}
            for pair in macro_pairs:
                try:
                    candles = await self.api.get_candles(pair, bar="4H", limit=50)
                    if candles:
                        from utils.indicators import candles_to_df, add_all_indicators
                        df = add_all_indicators(candles_to_df(candles))
                        last  = df.iloc[-1]
                        first = df.iloc[0]
                        market_raw[pair] = {
                            "price": last["close"],
                            "rsi":   float(last.get("rsi", 50)),
                            "change_pct": round((last["close"] - first["close"]) / first["close"] * 100, 1),
                            "trend": "alta" if last["close"] > df["close"].rolling(20).mean().iloc[-1] else "baixa",
                        }
                except Exception as e:
                    logger.warning(f"Macro data failed for {pair}: {e}")

            btc = market_raw.get("BTC-USDT", {})
            eth = market_raw.get("ETH-USDT", {})
            sol = market_raw.get("SOL-USDT", {})

            # ── Scan de convicção no 4H e 1D ────────────────────────────────
            conviction_signals = await scan_pairs(DEFAULT_PAIRS[:12], bar="4H")
            conviction_signals = sorted(
                [s for s in conviction_signals if s.get("rr_ratio", 0) >= 2.5 and s.get("confidence", 0) >= 75],
                key=lambda s: s.get("score", 0), reverse=True
            )[:3]

            # ── Calcula viés macro ───────────────────────────────────────────
            all_pairs_signals = await scan_pairs(DEFAULT_PAIRS, bar="1H")
            bullish_count = sum(1 for s in all_pairs_signals if s.get("direction") == "LONG")
            bearish_count = sum(1 for s in all_pairs_signals if s.get("direction") == "SHORT")
            total_scanned = len(DEFAULT_PAIRS)

            if bullish_count > bearish_count * 1.4:
                bias = "bullish"
            elif bearish_count > bullish_count * 1.4:
                bias = "bearish"
            else:
                bias = "neutro"

            btc_rsi = btc.get("rsi", 50)
            if btc_rsi > 70:
                bias = "bearish"
            elif btc_rsi < 35:
                bias = "bullish"

            # Fetch Fear & Greed Index
            fg = await fetch_fear_greed()

            week_str = datetime.now().strftime("%d/%m")
            market_data = {
                "week":                 week_str,
                "weekday":              weekday_name,
                "btc_price":            f"${btc.get('price', 0):,.0f}",
                "btc_rsi":              btc.get("rsi", 50),
                "btc_trend":            btc.get("trend", "lateral"),
                "btc_change":           btc.get("change_pct", 0.0),
                "eth_price":            f"${eth.get('price', 0):,.0f}",
                "eth_rsi":              eth.get("rsi", 50),
                "eth_trend":            eth.get("trend", "lateral"),
                "eth_change":           eth.get("change_pct", 0.0),
                "sol_price":            f"${sol.get('price', 0):,.0f}",
                "sol_rsi":              sol.get("rsi", 50),
                "sol_trend":            sol.get("trend", "lateral"),
                "btc_dominance":        "estimado ~55%" if btc.get("change_pct", 0) > eth.get("change_pct", 0) else "reduzindo",
                "bullish_count":        bullish_count,
                "bearish_count":        bearish_count,
                "total_pairs":          total_scanned,
                "conviction_count":     len(conviction_signals),
                "bias":                 bias,
                "fear_greed_value":     fg["value"],
                "fear_greed_label":     fg["label"],
                "fear_greed_yesterday": fg["yesterday"],
            }

            # ── Gera análise com LLM ─────────────────────────────────────────
            macro_text = await analyze_weekly_macro(market_data)

            # ── Formata e envia ──────────────────────────────────────────────
            msg = format_weekly_macro(
                macro_text,
                market_data,
                conviction_signals,
                ref_link=self.ref_link,
            )

            await self._send(msg)
            logger.info(f"Análise macro enviada — viés {bias}, {len(conviction_signals)} convicção(ões)")

        except Exception as e:
            logger.error(f"Erro ao gerar análise macro semanal: {e}")

    @staticmethod
    def _select_hedge_portfolio(signals: list, target: int = 6) -> tuple[list, str]:
        """Monta um portfolio com viés direcional + hedge parcial.

        Retorna (sinais_selecionados, bias_string).

        Lógica:
          - Calcula o viés do mercado pela proporção de LONGs/SHORTs disponíveis
          - bullish (>60% LONG)  → seleciona 4 LONG + 2 SHORT (ratio 2:1)
          - bearish (>60% SHORT) → seleciona 2 LONG + 4 SHORT
          - neutro               → seleciona 3 LONG + 3 SHORT
          - Seleciona os de maior score em cada direção
          - Se não há sinals suficientes em alguma direção, ajusta proporcional
        """
        longs  = sorted([s for s in signals if s.get("direction") == "LONG"],
                        key=lambda s: s.get("score", 0), reverse=True)
        shorts = sorted([s for s in signals if s.get("direction") == "SHORT"],
                        key=lambda s: s.get("score", 0), reverse=True)
        total  = len(longs) + len(shorts)
        if total == 0:
            return [], "neutro"

        long_ratio = len(longs) / total
        if long_ratio >= 0.60:
            bias = "bullish"
            n_l, n_s = min(4, len(longs)), min(2, len(shorts))
        elif long_ratio <= 0.40:
            bias = "bearish"
            n_l, n_s = min(2, len(longs)), min(4, len(shorts))
        else:
            bias = "neutro"
            half = target // 2
            n_l, n_s = min(half, len(longs)), min(half, len(shorts))

        selected = longs[:n_l] + shorts[:n_s]
        for s in selected:
            s["portfolio_bias"]    = bias
            s["portfolio_n_longs"] = n_l
            s["portfolio_n_shorts"] = n_s
        return selected, bias

    @staticmethod
    def _classify_setup(signal: dict, mode: str) -> str:
        """Classifica o setup como: scalp, swing, sniper, breakout, reversal, retest."""
        rr  = signal.get("rr_ratio", 0)
        reasons = " ".join(signal.get("reasons", [])).lower()
        if rr >= 4.5:
            return "sniper"
        if mode == "swing":
            return "swing"
        if any(k in reasons for k in ("divergên", "divergencia", "reversal", "reversão")):
            return "reversal"
        if any(k in reasons for k in ("breakout", "rompimento", "break")):
            return "breakout"
        if any(k in reasons for k in ("retest", "reteste", "retorno")):
            return "retest"
        if rr >= 3.0:
            return "premium"
        return "scalp"

    def _generate_portfolio_times(self, n: int = 6) -> list[datetime]:
        """Divide o dia de trading em n slots e sorteia um horário por slot.

        Janela: 09:30 → 21:30 (12h). Cada slot tem ~2h. O resultado garante que
        nenhum sinal saia muito próximo do outro e que cubram o dia inteiro.
        """
        from datetime import date as _date, time as _time
        start_h = 9.5    # 09:30
        end_h   = 21.5   # 21:30
        slot    = (end_h - start_h) / n
        today   = _date.today()
        times   = []
        for i in range(n):
            lo = start_h + i * slot + 0.10        # buffer de 6min nas bordas
            hi = start_h + (i + 1) * slot - 0.10
            rh = random.uniform(lo, hi)
            h, m = int(rh), int((rh % 1) * 60)
            times.append(datetime.combine(today, _time(h, m)))
        return times

    async def _register_trade(self, signal: dict) -> "ActiveTrade":
        """Adiciona trade ao tracker E salva no DB atomicamente.
        Ponto único de entrada para todo novo trade — garante persistência."""
        trade = self.tracker.add_trade(signal)
        await self.db.save_trade(trade.to_dict(), bankroll=self.bankroll)
        logger.info(f"[DB] Trade registrado: {signal['pair']} {signal['direction']} entry={signal['entry']}")
        return trade

    async def _persist_trade_event(self, trade: "ActiveTrade", event: str):
        """Salva estado atualizado do trade após evento (TP/SL) no DB."""
        trade_dict = trade.to_dict()
        pnl_usd = round(PerformanceDB.calc_pnl_usd(trade_dict, self.bankroll), 2)
        await self.db.save_trade(trade_dict, bankroll=self.bankroll)
        logger.info(f"[DB] Evento {event} — {trade.pair} | PNL: ${pnl_usd:+.2f}")
        return trade_dict, pnl_usd

    async def _send_pending_signal(self, pending: dict):
        """Envia um sinal individual da fila de portfolio."""
        signal   = pending["signal"]
        llm_mode = pending.get("llm_mode", "swing")

        signal["calc_link"] = self.calc_link
        analysis  = await analyze_signal(signal, mode=llm_mode)
        chart_buf = create_chart(signal, self.config)
        msg       = format_signal_message(signal, analysis=analysis,
                                          ref_link=self.ref_link, mode=llm_mode)

        logger.info(
            f"[PORTFOLIO AGENDADO] {signal['pair']} {signal['direction']} "
            f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')} "
            f"tp_count={signal.get('tp_count')}"
        )

        await self._register_trade(signal)
        await self._send(msg, photo=chart_buf)
        self._last_signal_at = datetime.now(timezone.utc)

    async def _scan_cycle(self, mission: dict = None) -> int:
        """Escaneia pares e envia sinais SEMPRE para BOT IA. mission = {bar, mode, max_signals}.

        Modos:
          portfolio — seleciona 4+2 ou 2+4 com hedge e agenda sinais ao longo do dia
          swing     — seleciona melhores sinais do 4H, RR≥2.0
          scalp     — seleciona sinais rápidos do 1H/15m
        """
        pairs          = self.config.get("pairs", DEFAULT_PAIRS)
        min_confidence = self.config.get("min_confidence", 50)

        if mission:
            bar      = mission.get("bar", "4H")
            mode     = mission.get("mode", "swing")
            max_sigs = mission.get("max_signals", 2)
        else:
            bar      = "4H"
            mode     = "swing"
            max_sigs = 2

        is_portfolio = (mode == "portfolio")

        # Proteção definitiva: portfolio só executa UMA vez por dia
        today_str = date.today().isoformat()
        if is_portfolio:
            if self._portfolio_sent_date == today_str:
                logger.warning("Portfolio já executado hoje — scan ignorado.")
                return 0
            self._portfolio_sent_date = today_str

        # Portfolio usa 4H com critério mais largo para ter sinais suficientes
        if is_portfolio:
            bar, min_rr, max_rr = "4H", 1.8, 6.0
        elif mode == "swing":
            min_rr, max_rr = 2.0, 6.0
        else:
            min_rr = self.config.get("min_rr", 1.5)
            max_rr = self.config.get("max_rr", 5.0)

        logger.info(f"Scan [{mode.upper()} {bar}] — {len(pairs)} pares, max {max_sigs}...")
        signals = await scan_pairs(pairs, bar=bar)

        filtered = [
            s for s in signals
            if s.get("rr_ratio", 0) >= min_rr
            and s.get("rr_ratio", 0) <= max_rr
            and s.get("confidence", 0) >= min_confidence
        ]

        # Seleção de sinais
        if is_portfolio:
            # Hedge portfolio: viés direcional 4+2 ou 2+4
            selected, bias = self._select_hedge_portfolio(filtered, target=6)
        else:
            selected = sorted(filtered, key=lambda s: s.get("score", 0), reverse=True)[:max_sigs]
            bias = None

        if not selected:
            logger.info(f"Nenhum sinal válido [{mode} {bar}]")
            return 0

        logger.info(f"{len(selected)} sinal(is) selecionado(s) [{mode}]"
                    + (f" — viés {bias}" if bias else ""))

        # Carrega stats de sizing uma vez por ciclo
        try:
            sizing_stats = await self.db.get_sizing_stats(bankroll=self.bankroll)
        except Exception:
            sizing_stats = {}

        _SCALP_BARS = {"1m", "3m", "5m", "15m", "30m"}
        _SWING_BARS = {"4H", "1D", "3D", "1W"}

        # Portfolio: calcula sizing, envia header agora e agenda sinais ao longo do dia
        if is_portfolio and len(selected) < 2:
            logger.info("Portfolio: sinais insuficientes — nenhum envio hoje.")
            return 0

        if is_portfolio:
            for s in selected:
                risk_pct, sizing_reason = calculate_risk_pct(s, sizing_stats)
                s["risk_pct"]    = risk_pct
                s["sizing_info"] = sizing_reason

            # Agenda cada sinal num horário aleatório ao longo do dia
            send_times = self._generate_portfolio_times(len(selected))
            for signal, send_at in zip(selected, send_times):
                signal["trade_mode"] = "swing"
                signal["setup_type"] = self._classify_setup(signal, "swing")
                signal["trade_style"] = signal.get("trade_style") or "swing"
                signal["bankroll"] = self.bankroll
                self._pending_signals.append({
                    "send_at":  send_at,
                    "signal":   signal,
                    "llm_mode": "swing",
                })
            self._pending_signals.sort(key=lambda p: p["send_at"])
            next_times = ", ".join(
                p["signal"]["pair"] + "@" + p["send_at"].strftime("%H:%M")
                for p in self._pending_signals
            )
            logger.info(f"Portfolio agendado: {next_times}")
            return len(selected)

        for signal in selected:
            setup_type = self._classify_setup(signal, "swing" if is_portfolio else mode)
            signal["trade_mode"] = "swing" if is_portfolio else mode
            signal["setup_type"] = setup_type

            # Assign trade_style from signal (already set by detect_signal) or derive
            if not signal.get("trade_style"):
                tf_up = bar.upper()
                if tf_up in {b.upper() for b in _SCALP_BARS}:
                    signal["trade_style"] = "scalp"
                elif tf_up in {b.upper() for b in _SWING_BARS}:
                    signal["trade_style"] = "swing"
                else:
                    signal["trade_style"] = "daytrade"

            # LLM mode: use trade_style to pick prompt
            llm_mode = signal["trade_style"] if signal["trade_style"] in ("scalp", "daytrade", "swing") else "swing"
            if is_portfolio:
                llm_mode = "swing"

            # Sizing dinâmico (já calculado no portfolio, calcula agora para outros modos)
            if not is_portfolio:
                risk_pct, sizing_reason = calculate_risk_pct(signal, sizing_stats)
                signal["risk_pct"]    = risk_pct
                signal["sizing_info"] = sizing_reason
            signal["bankroll"] = self.bankroll

            await self._register_trade(signal)
            analysis   = await analyze_signal(signal, mode=llm_mode)
            chart_buf  = create_chart(signal, self.config)
            msg        = format_signal_message(signal, analysis=analysis,
                                               ref_link=self.ref_link,
                                               mode=llm_mode)

            logger.info(
                f"[{setup_type.upper()}] {signal['pair']} {signal['direction']} "
                f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')} "
                f"risk={signal.get('risk_pct')}% bar={bar}"
            )

            await self._send(msg, photo=chart_buf)
            self._last_signal_at = datetime.now(timezone.utc)
            await asyncio.sleep(2)  # pausa entre sinais do portfolio

        return len(selected)

    async def _check_gap_events(self):
        """Após restart, verifica candles 1m recentes para detectar SL/TP que bateram
        enquanto o bot estava offline. Resolve o 'gap problem' de downtime.

        Lógica por candle (1m, últimos 30 min):
          - LONG: low <= SL → SL_HIT | high >= TP → TP_HIT
          - SHORT: high >= SL → SL_HIT | low <= TP → TP_HIT
          - Se candle é vermelho (close < open) → SL tem prioridade sobre TP
          - Se candle é verde (close > open) → TP tem prioridade
        """
        if not self.tracker.active_trades:
            return

        logger.info(f"[GAP CHECK] Verificando {len(self.tracker.active_trades)} trade(s) pós-restart...")

        for pair, trade in list(self.tracker.active_trades.items()):
            try:
                candles = await self.api.get_candles(pair, bar="1m", limit=30)
                if not candles:
                    continue

                event_fired = None
                event_price = None

                for candle in candles:
                    # Formato BloFin: [ts, open, high, low, close, ...]
                    try:
                        c_open  = float(candle[1])
                        c_high  = float(candle[2])
                        c_low   = float(candle[3])
                        c_close = float(candle[4])
                    except (IndexError, ValueError):
                        continue

                    is_red = c_close < c_open  # candle vermelho → SL tem prioridade

                    if trade.direction == "LONG":
                        sl_touched = c_low  <= trade.stop_loss
                        tp1_touch  = not trade.tp1_hit and trade.tp1 > 0 and c_high >= trade.tp1
                        tp2_touch  = not trade.tp2_hit and trade.tp2 > 0 and c_high >= trade.tp2
                        tp3_touch  = not trade.tp3_hit and trade.tp3 > 0 and c_high >= trade.tp3

                        if is_red and sl_touched:
                            event = trade.check_levels(trade.stop_loss)
                        elif tp3_touch:
                            event = trade.check_levels(trade.tp3)
                        elif tp2_touch:
                            event = trade.check_levels(trade.tp2)
                        elif tp1_touch:
                            event = trade.check_levels(trade.tp1)
                        elif sl_touched:
                            event = trade.check_levels(trade.stop_loss)
                        else:
                            event = None
                    else:  # SHORT
                        sl_touched = c_high >= trade.stop_loss
                        tp1_touch  = not trade.tp1_hit and trade.tp1 > 0 and c_low <= trade.tp1
                        tp2_touch  = not trade.tp2_hit and trade.tp2 > 0 and c_low <= trade.tp2
                        tp3_touch  = not trade.tp3_hit and trade.tp3 > 0 and c_low <= trade.tp3

                        if not is_red and sl_touched:
                            event = trade.check_levels(trade.stop_loss)
                        elif tp3_touch:
                            event = trade.check_levels(trade.tp3)
                        elif tp2_touch:
                            event = trade.check_levels(trade.tp2)
                        elif tp1_touch:
                            event = trade.check_levels(trade.tp1)
                        elif sl_touched:
                            event = trade.check_levels(trade.stop_loss)
                        else:
                            event = None

                    if event:
                        event_fired = event
                        trade_dict = trade.to_dict()
                        pnl_usd = round(PerformanceDB.calc_pnl_usd(trade_dict, self.bankroll), 2)
                        logger.info(f"[GAP {event}] {pair} detectado nos candles pós-restart | PNL: ${pnl_usd:+.2f}")
                        msg = format_update_message(pair, event, trade_dict, bankroll=self.bankroll)
                        await self._send(msg)
                        await self.db.save_trade(trade_dict, bankroll=self.bankroll)

                        if event == "SL_HIT" or event == trade.final_tp:
                            self.tracker.remove_trade(pair)
                            break  # trade encerrado, para de processar candles

            except Exception as e:
                logger.error(f"[GAP CHECK] Erro em {pair}: {e}")

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
                trade_dict, pnl_usd = await self._persist_trade_event(trade, event)
                logger.info(f"[{event}] {pair} @ {price:.4f} | PNL: ${pnl_usd:+.2f} ({trade_dict['pnl_pct']:+.2f}%)")

                msg = format_update_message(pair, event, trade_dict, bankroll=self.bankroll)
                await self._send(msg)

                events_fired.append(event)

                if event == "SL_HIT" or event == trade.final_tp:
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
        """Gera N scans independentes em horários aleatórios ao longo do dia.

        Cada scan roda na hora marcada com dados FRESCOS e envia 1 sinal imediatamente.
        Dias úteis: 6 scans | Fim de semana: 4 scans.
        Janela: 09:00 → 21:30. Slots iguais, 1 horário aleatório por slot.
        Restart após início do dia: ignora slots já passados — não perde o dia todo.
        """
        today   = date.today()
        weekday = today.weekday()  # 0=Seg … 6=Dom
        now     = datetime.now()

        # Fim de semana: menos scans (mercado menos líquido)
        n_total = 4 if weekday in (5, 6) else 6

        # 3 períodos fixos: manhã | tarde | noite
        # Os N scans são distribuídos proporcionalmente entre eles
        _periods = [
            (9.0,  13.0),   # Manhã:  09:00 – 13:00
            (13.0, 18.0),   # Tarde:  13:00 – 18:00
            (18.0, 22.5),   # Noite:  18:00 – 22:30
        ]
        # Ex: 6 scans → 2 por período | 4 scans → 1-2-1
        per_period = max(1, n_total // 3)
        slots_per_period = [per_period] * 3
        # distribui resto nos primeiros períodos
        for i in range(n_total - sum(slots_per_period)):
            slots_per_period[i] += 1

        # Padrão alternado de timeframes para cobrir scalp + swing
        _bars  = ["1H", "4H", "1H", "4H", "1H", "4H"]
        _modes = ["scalp", "swing", "scalp", "swing", "scalp", "swing"]

        missions = []
        idx = 0
        for p_idx, (p_start, p_end) in enumerate(_periods):
            n_in_period = slots_per_period[p_idx]
            slot = (p_end - p_start) / n_in_period
            for j in range(n_in_period):
                lo = p_start + j * slot + 0.05
                hi = p_start + (j + 1) * slot - 0.05
                rh = random.uniform(lo, hi)
                h, m = int(rh), int((rh % 1) * 60)
                t = datetime.combine(today, time(h, m))
                bar_idx = idx
                idx += 1

                # Slots já passados são ignorados (restart no meio do dia não perde tudo)
                if t <= now:
                    logger.info(f"Slot {bar_idx+1} ({t.strftime('%H:%M')}) já passou — ignorado.")
                    continue

                missions.append({
                    "time":        t,
                    "bar":         _bars[bar_idx % len(_bars)],
                    "mode":        _modes[bar_idx % len(_modes)],
                    "max_signals": 1,
                })

        self._today_schedule = [m["time"] for m in missions]

        day_name = ['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'][weekday]
        times_str = ", ".join(
            f"{m['time'].strftime('%H:%M')}[{m['bar']}]" for m in missions
        )
        logger.info(
            f"Agenda [{day_name}] {len(missions)} missão(ões): {times_str}"
        )
        return missions

    async def _background_loop(self):
        """Loop de background: scan automático por agenda + atualização de trades."""
        update_interval = self.config.get("update_interval", 60)
        logger.info(f"Background loop iniciado (update trades: {update_interval}s)")

        # Gera agenda para hoje (lista de missões)
        missions   = self._schedule_daily_scans()
        current_day = date.today()

        while True:
            try:
                now = datetime.now()

                # Virada do dia — gera nova agenda e limpa fila pendente do dia anterior
                if now.date() != current_day:
                    current_day = now.date()
                    self._pending_signals.clear()
                    self._portfolio_sent_date = ""
                    self._morning_sent_date = ""
                    missions = self._schedule_daily_scans()

                    # Domingo 20h → resumo semanal automático
                    if now.weekday() == 6 and now.hour == 20:
                        try:
                            stats = await self.db.get_stats(days=7, bankroll=self.bankroll)
                            recap = format_weekly_recap(stats, starting_bankroll=self.bankroll)
                            await self._send(recap)
                            logger.info("Resumo semanal enviado.")
                        except Exception as e:
                            logger.error(f"Erro ao enviar resumo semanal: {e}")

                    # Segunda-feira 8h → análise macro semanal
                    if now.weekday() == 0 and now.hour == 8:
                        await self._send_weekly_macro(weekday_name="Segunda-feira")

                    # Quinta-feira 8h → segunda análise macro (se volatilidade alta)
                    if now.weekday() == 3 and now.hour == 8:
                        try:
                            btc_candles = await self.api.get_candles("BTC-USDT", bar="4H", limit=20)
                            if btc_candles:
                                from utils.indicators import candles_to_df, add_all_indicators
                                btc_df = add_all_indicators(candles_to_df(btc_candles))
                                btc_atr = float(btc_df["atr"].iloc[-1]) if "atr" in btc_df.columns else 0
                                btc_price = float(btc_df["close"].iloc[-1])
                                atr_pct = btc_atr / btc_price * 100 if btc_price > 0 else 0
                                if atr_pct >= 1.5:  # ATR ≥ 1.5% do preço → alta volatilidade
                                    logger.info(f"Alta volatilidade detectada (ATR={atr_pct:.2f}%) — enviando análise quinta")
                                    await self._send_weekly_macro(weekday_name="Quinta-feira")
                        except Exception as e:
                            logger.warning(f"Erro ao checar volatilidade BTC: {e}")

                # 08:00 BRT (11:00 UTC) → mensagem de bom dia com preço do BTC
                today_str = now.date().isoformat()
                if now.hour == 11 and self._morning_sent_date != today_str:
                    self._morning_sent_date = today_str
                    await self._send_morning_message()

                if self.running:
                    # Atualiza trades ativos a cada tick
                    await self._update_trades()

                    # Envia sinais do portfolio agendados cujo horário chegou
                    due_sigs = [p for p in self._pending_signals if p["send_at"] <= now]
                    self._pending_signals = [p for p in self._pending_signals if p["send_at"] > now]
                    for pending in due_sigs:
                        try:
                            await self._send_pending_signal(pending)
                        except Exception as e:
                            logger.error(f"Erro ao enviar sinal agendado {pending['signal'].get('pair')}: {e}")

                    # Dispara missões cujo horário já passou
                    due      = [m for m in missions if m["time"] <= now]
                    missions = [m for m in missions if m["time"] > now]
                    if due:
                        remaining_times = [m["time"].strftime("%H:%M") for m in missions]
                        logger.info(f"Executando {len(due)} missão(ões) — próximas: {remaining_times}")
                        for mission in due:
                            await self._scan_cycle(mission=mission)

            except Exception as e:
                logger.error(f"Erro no ciclo: {e}")

            await asyncio.sleep(update_interval)

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def _health_check_loop(self):
        """Duas funções:
        1. Auto-ping a cada 10 min para evitar sleep no Render free tier
        2. Alerta admin se nenhum sinal foi enviado em 25h+
        """
        self_url = os.getenv("RENDER_EXTERNAL_URL", "")  # Render injeta automaticamente
        ping_interval = 10 * 60  # 10 minutos

        await asyncio.sleep(60)  # aguarda bot inicializar antes do primeiro ping

        tick = 0
        while self.running:
            # ── Auto-ping para manter o serviço acordado ────────────────
            if self_url:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self_url}/health", timeout=aiohttp.ClientTimeout(total=10)) as r:
                            logger.debug(f"Self-ping: {r.status}")
                except Exception as e:
                    logger.debug(f"Self-ping falhou (normal se offline): {e}")

            # ── Alerta admin se sem sinais por 25h (a cada 1h = 6 ticks) ─
            tick += 1
            if tick % 6 == 0:
                try:
                    if self._last_signal_at:
                        hours_since = (datetime.now(timezone.utc) - self._last_signal_at).total_seconds() / 3600
                        if hours_since > 25 and self.admin_id:
                            bot = self._app.bot if hasattr(self, "_app") else None
                            if bot:
                                await bot.send_message(
                                    chat_id=self.admin_id,
                                    text=f"⚠️ *SidQuant Bot — Alerta*\n\nNenhum sinal enviado há {hours_since:.0f}h.\nVerifique se o bot está rodando.",
                                    parse_mode="Markdown",
                                )
                except Exception as e:
                    logger.error("Health check error: %s", e)

            await asyncio.sleep(ping_interval)

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

        # Recarrega trades abertos do DB preservando estado (tp1_hit, tp2_hit etc.)
        try:
            import json as _json
            open_trades = await self.db.get_open_trades()
            for t in open_trades:
                if isinstance(t.get("reasons"), str):
                    try:
                        t["reasons"] = _json.loads(t["reasons"])
                    except Exception:
                        t["reasons"] = []
                self.tracker.restore_from_db_row(t)
            if open_trades:
                pairs = ", ".join(t["pair"] for t in open_trades)
                logger.info(f"✅ {len(open_trades)} trade(s) recarregado(s) do DB: {pairs}")
            else:
                logger.info("Nenhum trade aberto no DB para recarregar.")
        except Exception as e:
            logger.warning(f"Erro ao recarregar trades abertos: {e}")

        self._app = Application.builder().token(self.token).build()
        self.payment_manager.set_bot_app(self._app)

        self._app.add_handler(CommandHandler("start", self.cmd_start))
        self._app.add_handler(CommandHandler("scan", self.cmd_scan))
        self._app.add_handler(CommandHandler("trades", self.cmd_trades))
        self._app.add_handler(CommandHandler("stats", self.cmd_stats))
        self._app.add_handler(CommandHandler("performance", self.cmd_performance))
        self._app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self._app.add_handler(CommandHandler("stop", self.cmd_stop))
        self._app.add_handler(CommandHandler("resume", self.cmd_resume))
        self._app.add_handler(CommandHandler("enable", self.cmd_enable))
        self._app.add_handler(CommandHandler("disable", self.cmd_disable))
        self._app.add_handler(CommandHandler("groups", self.cmd_groups))
        self._app.add_handler(CommandHandler("cleartrades", self.cmd_cleartrades))
        self._app.add_handler(CommandHandler("resetall", self.cmd_resetall))
        self._app.add_handler(CommandHandler("forcescan", self.cmd_forcescan))
        self._app.add_handler(CommandHandler("signal", self.cmd_signal))
        self._app.add_handler(CommandHandler("newtrade", self.cmd_newtrade))
        self._app.add_handler(CommandHandler("agenda", self.cmd_agenda))
        self._app.add_handler(CommandHandler("broadcast", self.cmd_broadcast))
        self._app.add_handler(CommandHandler("macro", self.cmd_macro))
        self._app.add_handler(CommandHandler("share", self.cmd_share))
        # Fase 9 — Agente Educacional
        self._app.add_handler(CommandHandler("ask", self.cmd_ask))
        self._app.add_handler(CommandHandler("mentor", self.cmd_mentor))
        self._app.add_handler(CommandHandler("reloadkb", self.cmd_reloadkb))
        self._app.add_handler(CommandHandler("addvip", self.cmd_addvip))
        self._app.add_handler(CommandHandler("removevip", self.cmd_removevip))
        # Fase 10 — Checkout automático
        self._app.add_handler(CommandHandler("minhaconta", self.cmd_minhaconta))
        self._app.add_handler(ChatMemberHandler(self.on_bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

        logger.info("Bot iniciando...")

        async with self._app:
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)

            # Dashboard web — usa PORT do Render ou fallback 8080
            dashboard_port = int(os.getenv("PORT", self.config.get("dashboard_port", 8080)))
            from dashboard import create_dashboard
            dash_app = create_dashboard(self)
            dash_runner = aiohttp_web.AppRunner(dash_app)
            await dash_runner.setup()
            dash_site = aiohttp_web.TCPSite(dash_runner, "0.0.0.0", dashboard_port)
            await dash_site.start()
            logger.info(f"Dashboard rodando em http://localhost:{dashboard_port}")

            # Verifica se SL/TP bateu durante o downtime antes de iniciar o loop
            await self._check_gap_events()

            bg_task = asyncio.create_task(self._background_loop())
            hc_task = asyncio.create_task(self._health_check_loop())
            logger.info("Bot rodando. Pressione Ctrl+C para parar.")

            try:
                while True:
                    await asyncio.sleep(1)
            except (KeyboardInterrupt, asyncio.CancelledError):
                pass
            finally:
                bg_task.cancel()
                hc_task.cancel()
                try:
                    await bg_task
                except asyncio.CancelledError:
                    pass
                try:
                    await hc_task
                except asyncio.CancelledError:
                    pass
                await dash_runner.cleanup()
                await self._app.updater.stop()
                await self._app.stop()
                await self.api.close()
                await self.db.close()
                logger.info("Bot encerrado.")


def main():
    import time as _time
    config = load_config()
    retry_delay = 30  # segundos entre tentativas

    while True:
        try:
            bot = BloFinBot(config)
            asyncio.run(bot.run())
            break  # saída limpa (Ctrl+C ou stop normal)
        except KeyboardInterrupt:
            logger.info("Bot encerrado pelo usuário.")
            break
        except Exception as e:
            logger.error(f"Bot encerrado com erro: {e}. Reiniciando em {retry_delay}s...")
            _time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 300)  # backoff até 5 min


if __name__ == "__main__":
    main()
