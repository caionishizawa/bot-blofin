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
    format_weekly_recap,
    format_weekly_macro,
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
        if not self.admin_ids:
            return False  # bloqueia tudo se ADMIN_IDS não estiver configurado
        return str(update.effective_user.id) in self.admin_ids

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
            lines.append(f"{status} `{t.strftime('%H:%M')}`  _BRT_")
        lines.append("")
        lines.append(f"_Bot está {'▶️ rodando' if self.running else '⏹ pausado'}_")
        await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

    async def cmd_macro(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Dispara manualmente a análise macro semanal."""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return
        msg = await update.message.reply_text("📊 Gerando análise macro semanal...")
        await self._send_weekly_macro()
        await msg.edit_text("✅ Análise macro enviada.")

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

    async def _send_weekly_macro(self):
        """Segunda-feira: coleta dados de mercado, gera análise macro e entradas de convicção."""
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

            week_str = datetime.now().strftime("%d/%m")
            market_data = {
                "week":            week_str,
                "btc_price":       f"${btc.get('price', 0):,.0f}",
                "btc_rsi":         btc.get("rsi", 50),
                "btc_trend":       btc.get("trend", "lateral"),
                "btc_change":      btc.get("change_pct", 0.0),
                "eth_price":       f"${eth.get('price', 0):,.0f}",
                "eth_rsi":         eth.get("rsi", 50),
                "eth_trend":       eth.get("trend", "lateral"),
                "eth_change":      eth.get("change_pct", 0.0),
                "sol_price":       f"${sol.get('price', 0):,.0f}",
                "sol_rsi":         sol.get("rsi", 50),
                "sol_trend":       sol.get("trend", "lateral"),
                "btc_dominance":   "estimado ~55%" if btc.get("change_pct", 0) > eth.get("change_pct", 0) else "reduzindo",
                "bullish_count":   bullish_count,
                "bearish_count":   bearish_count,
                "total_pairs":     total_scanned,
                "conviction_count": len(conviction_signals),
                "bias":            bias,
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

            targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
            if self.channel_id and self.channel_id not in targets:
                targets.append(self.channel_id)
            for target in targets:
                await self._send(msg, chat_id=target)

            logger.info(f"Análise macro enviada — viés {bias}, {len(conviction_signals)} convicção(ões)")

        except Exception as e:
            logger.error(f"Erro ao gerar análise macro semanal: {e}")

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

    async def _scan_cycle(self, mission: dict = None, chat_id: str = None) -> int:
        """Escaneia pares e envia sinais. mission = {bar, mode, max_signals}."""
        pairs          = self.config.get("pairs", DEFAULT_PAIRS)
        min_confidence = self.config.get("min_confidence", 50)

        if mission:
            bar        = mission.get("bar", "1H")
            mode       = mission.get("mode", "scalp")
            max_sigs   = mission.get("max_signals", 2)
        else:
            bar      = self.config.get("timeframe", "1H")
            mode     = "scalp"
            max_sigs = 2

        min_rr = self.config.get("min_rr", 1.5)
        max_rr = self.config.get("max_rr", 5.0)
        if mode == "swing":
            min_rr, max_rr = 2.0, 5.0

        logger.info(f"Scan [{mode.upper()} {bar}] — {len(pairs)} pares, max {max_sigs} sinal(is)...")
        signals = await scan_pairs(pairs, bar=bar)

        filtered = [
            s for s in signals
            if s.get("rr_ratio", 0) >= min_rr
            and s.get("rr_ratio", 0) <= max_rr
            and s.get("confidence", 0) >= min_confidence
        ]

        # Ordena por score e limita ao máximo da janela
        filtered = sorted(filtered, key=lambda s: s.get("score", 0), reverse=True)[:max_sigs]
        logger.info(f"{len(filtered)} sinal(is) selecionado(s) [{mode}]")

        risk_pct = float(self.config.get("risk_pct_per_trade", 2.0))
        for signal in filtered:
            setup_type = self._classify_setup(signal, mode)
            signal["trade_mode"]  = mode
            signal["setup_type"]  = setup_type
            signal["risk_pct"]    = risk_pct
            signal["bankroll"]    = self.bankroll

            if mode == "swing":
                signal["swing_override_lev"] = 4

            trade = self.tracker.add_trade(signal)
            await self.db.save_trade(trade.to_dict(), bankroll=self.bankroll)
            analysis  = await analyze_signal(signal, mode=mode)
            chart_buf = create_chart(signal, self.config)
            msg       = format_signal_message(signal, analysis=analysis, ref_link=self.ref_link, mode=mode)

            logger.info(
                f"[{setup_type.upper()}] {signal['pair']} {signal['direction']} "
                f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')} bar={bar}"
            )

            targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
            if chat_id and chat_id not in targets:
                targets.append(chat_id)
            if not targets and self.vip_channel_id:
                targets = [self.vip_channel_id]

            for target in targets:
                await self._send(msg, photo=chart_buf, chat_id=target)

            self._last_signal_at = datetime.now(timezone.utc)

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
                    # Post teaser to FREE channel after trade closes
                    if self.free_channel_id and self.free_channel_id != self.vip_channel_id:
                        result_emoji = "✅" if trade_dict.get("pnl_usd", 0) > 0 else "❌"
                        pnl_usd = trade_dict.get("pnl_usd", 0)
                        direction = trade_dict.get("direction", "LONG")
                        teaser = (
                            f"{result_emoji} *Resultado do sinal VIP — {pair}*\n\n"
                            f"Direção: `{direction}`\n"
                            f"PNL: `{'+'if pnl_usd>=0 else ''}{pnl_usd:.2f} USD`\n\n"
                            f"Quer pegar o próximo *antes de acontecer*?\n"
                            f"👇 Acesse o VIP: {self.config.get('ref_link', os.getenv('TELEGRAM_REF_LINK', ''))}\n\n"
                            f"⚠️ Não é recomendação de investimento."
                        )
                        try:
                            await self._send(teaser, chat_id=self.free_channel_id)
                        except Exception:
                            pass

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
        """Gera missões de scan variando por dia da semana.

        Retorna lista de dicts: {time, bar, mode, max_signals}

        Segunda/Qua/Sex (dias ativos): 8-10 janelas, mix scalp+sniper
        Terça/Quinta (swing days): 6-8 janelas, inclui 4H swing
        Sábado/Domingo: 4-6 janelas, mais leve
        """
        today   = date.today()
        weekday = today.weekday()  # 0=Seg … 6=Dom

        # (anchor_time, spread_min, bar, mode, max_signals)
        if weekday in (5, 6):  # FDS — seletivo
            templates = [
                (time(9,  0), 20, "1H",  "scalp", 1),
                (time(12, 0), 30, "4H",  "swing", 1),
                (time(16, 0), 20, "1H",  "scalp", 1),
                (time(20, 30), 25, "4H", "swing", 1),
            ]
            bonus_chance = 0.25
        elif weekday in (1, 3):  # Ter/Qui — swing + scalp
            templates = [
                (time(8,  45), 15, "1H",  "scalp", 1),
                (time(10, 30), 20, "15m", "scalp", 1),
                (time(13,  0), 20, "4H",  "swing", 1),
                (time(15, 30), 15, "1H",  "scalp", 2),
                (time(18,  0), 20, "4H",  "swing", 1),
                (time(20, 30), 25, "1H",  "scalp", 1),
            ]
            bonus_chance = 0.40
        else:  # Seg/Qua/Sex — dias ativos, foco scalp
            templates = [
                (time(8,  30), 15, "15m", "scalp", 1),
                (time(9,  15), 20, "1H",  "scalp", 2),
                (time(11,  0), 15, "15m", "scalp", 1),
                (time(13, 30), 20, "1H",  "scalp", 1),
                (time(15, 30), 15, "1H",  "scalp", 2),
                (time(17, 15), 20, "15m", "scalp", 1),
                (time(19,  0), 20, "1H",  "scalp", 1),
                (time(21,  0), 25, "4H",  "swing", 1),
            ]
            bonus_chance = 0.50

        missions = []
        for anchor_t, spread, bar, mode, max_sigs in templates:
            base   = datetime.combine(today, anchor_t)
            offset = random.randint(-spread, spread)
            missions.append({
                "time":        base + timedelta(minutes=offset),
                "bar":         bar,
                "mode":        mode,
                "max_signals": max_sigs,
            })

        # Scan bônus surpresa
        if random.random() < bonus_chance:
            bonus_h = random.randint(10, 20)
            bonus_m = random.randint(0, 59)
            missions.append({
                "time":        datetime.combine(today, time(bonus_h, bonus_m)),
                "bar":         random.choice(["1H", "4H"]),
                "mode":        random.choice(["scalp", "swing"]),
                "max_signals": 1,
            })

        missions.sort(key=lambda m: m["time"])
        self._today_schedule = [m["time"] for m in missions]

        logger.info(
            f"Agenda [{['Seg','Ter','Qua','Qui','Sex','Sab','Dom'][weekday]}] "
            f"{len(missions)} missões: "
            + ", ".join(f"{m['time'].strftime('%H:%M')}[{m['bar']}]" for m in missions)
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

                # Virada do dia — gera nova agenda
                if now.date() != current_day:
                    current_day = now.date()
                    missions = self._schedule_daily_scans()

                    # Domingo 20h → resumo semanal automático
                    if now.weekday() == 6 and now.hour == 20:
                        try:
                            stats = await self.db.get_stats(days=7, bankroll=self.bankroll)
                            recap = format_weekly_recap(stats, starting_bankroll=self.bankroll)
                            targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
                            if self.channel_id and self.channel_id not in targets:
                                targets.append(self.channel_id)
                            for target in targets:
                                await self._send(recap, chat_id=target)
                            logger.info("Resumo semanal enviado.")
                        except Exception as e:
                            logger.error(f"Erro ao enviar resumo semanal: {e}")

                    # Segunda-feira 8h → análise macro + entradas de convicção
                    if now.weekday() == 0 and now.hour == 8:
                        await self._send_weekly_macro()

                if self.running:
                    # Atualiza trades ativos a cada tick
                    await self._update_trades()

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
        """Alert admin if no signal has been sent in 25+ hours."""
        await asyncio.sleep(3600)  # first check after 1h
        while self.running:
            try:
                if self._last_signal_at:
                    hours_since = (datetime.now(timezone.utc) - self._last_signal_at).total_seconds() / 3600
                    if hours_since > 25 and self.admin_id:
                        bot = self._app.bot if hasattr(self, "_app") else None
                        if bot:
                            await bot.send_message(
                                chat_id=self.admin_id,
                                text=f"⚠️ *BloFin Bot — Alerta*\n\nNenhum sinal enviado há {hours_since:.0f}h.\nVerifique se o bot está rodando corretamente.",
                                parse_mode="Markdown",
                            )
            except Exception as e:
                logger.error("Health check error: %s", e)
            await asyncio.sleep(3600)  # check every hour

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
        self._app.add_handler(CommandHandler("macro", self.cmd_macro))
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
    config = load_config()
    bot = BloFinBot(config)
    asyncio.run(bot.run())


if __name__ == "__main__":
    main()
