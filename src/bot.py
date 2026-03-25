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
            "👋 *SidQuant Bot* — Online!\n\n"
            "📡 *Sinais:*\n"
            "🔍 /scan — Escanear pares agora\n"
            "📋 /trades — Trades ativos\n"
            "📈 /stats — Performance semanal/mensal/anual\n"
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
            await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
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

        await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

    async def cmd_ask(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Responde dúvida de trading. FREE: 3/dia | VIP: ilimitado."""
        user_id = str(update.effective_user.id)
        question = " ".join(ctx.args) if ctx.args else ""

        if not question:
            await update.message.reply_text(
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
                await update.message.reply_text(
                    f"⏳ Você atingiu o limite de *{FREE_DAILY_LIMIT} perguntas/dia* no plano FREE.\n\n"
                    f"Quer respostas ilimitadas + mais detalhadas?\n"
                    f"👉 Acesse o VIP: {self.ref_link or 'https://partner.blofin.com/d/sideradog'}",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

        # Feedback de carregamento
        msg = await update.message.reply_text("🤖 Pensando...")

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
            await update.message.reply_text(
                "⭐ O modo `/mentor` é exclusivo para assinantes *VIP*.\n\n"
                f"👉 Acesse o VIP: {self.ref_link or 'https://partner.blofin.com/d/sideradog'}\n\n"
                "No plano FREE, use `/ask sua pergunta` para até 3 perguntas/dia.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        await update.message.reply_text(
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
            await update.message.reply_text("⛔ Acesso restrito.")
            return
        reload_knowledge_base()
        await update.message.reply_text("✅ Knowledge base recarregada com sucesso.")

    async def cmd_addvip(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: adiciona usuário à lista VIP em memória. Uso: /addvip <telegram_id>"""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return
        if not ctx.args:
            await update.message.reply_text("Uso: `/addvip <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
            return
        vip_id = ctx.args[0].strip()
        self._vip_ids.add(vip_id)
        await update.message.reply_text(f"✅ Usuário `{vip_id}` adicionado ao VIP.", parse_mode=ParseMode.MARKDOWN)
        logger.info(f"VIP adicionado: {vip_id}")

    async def cmd_removevip(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        """Admin: remove usuário do VIP. Uso: /removevip <telegram_id>"""
        if not self._is_admin(update):
            await update.message.reply_text("⛔ Acesso restrito.")
            return
        if not ctx.args:
            await update.message.reply_text("Uso: `/removevip <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
            return
        vip_id = ctx.args[0].strip()
        self._vip_ids.discard(vip_id)
        await update.message.reply_text(f"✅ Usuário `{vip_id}` removido do VIP.", parse_mode=ParseMode.MARKDOWN)
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

    async def _scan_cycle(self, mission: dict = None, chat_id: str = None) -> int:
        """Escaneia pares e envia sinais. mission = {bar, mode, max_signals}.

        Modos:
          portfolio — seleciona 4+2 ou 2+4 com hedge e envia header do dia
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

        targets = [g["chat_id"] for g in await self.db.get_enabled_groups()]
        if chat_id and chat_id not in targets:
            targets.append(chat_id)
        if not targets and self.vip_channel_id:
            targets = [self.vip_channel_id]
        if self.free_channel_id and self.free_channel_id not in targets:
            targets.append(self.free_channel_id)

        # Portfolio: envia header primeiro
        if is_portfolio and len(selected) >= 2:
            # Calcula sizing antes para mostrar risco total no header
            for s in selected:
                risk_pct, sizing_reason = calculate_risk_pct(s, sizing_stats)
                s["risk_pct"]    = risk_pct
                s["sizing_info"] = sizing_reason
            header_msg = format_portfolio_header(selected, bias, ref_link=self.ref_link)
            for target in targets:
                await self._send(header_msg, chat_id=target)
            await asyncio.sleep(1)

        for signal in selected:
            setup_type = self._classify_setup(signal, "swing" if is_portfolio else mode)
            signal["trade_mode"] = "swing" if is_portfolio else mode
            signal["setup_type"] = setup_type

            # Sizing dinâmico (já calculado no portfolio, calcula agora para outros modos)
            if not is_portfolio:
                risk_pct, sizing_reason = calculate_risk_pct(signal, sizing_stats)
                signal["risk_pct"]    = risk_pct
                signal["sizing_info"] = sizing_reason
            signal["bankroll"] = self.bankroll

            trade      = self.tracker.add_trade(signal)
            await self.db.save_trade(trade.to_dict(), bankroll=self.bankroll)
            analysis   = await analyze_signal(signal, mode="swing" if is_portfolio else mode)
            chart_buf  = create_chart(signal, self.config)
            msg        = format_signal_message(signal, analysis=analysis,
                                               ref_link=self.ref_link,
                                               mode="swing" if is_portfolio else mode)

            logger.info(
                f"[{setup_type.upper()}] {signal['pair']} {signal['direction']} "
                f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')} "
                f"risk={signal.get('risk_pct')}% bar={bar}"
            )

            for target in targets:
                await self._send(msg, photo=chart_buf, chat_id=target)

            self._last_signal_at = datetime.now(timezone.utc)
            await asyncio.sleep(2)  # pausa entre sinais do portfolio

        return len(selected)

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
        """Gera missões de scan variando por dia da semana.

        Estratégia: foco em swing/longo prazo (4H).
        Portfolio matinal: 1 scan 4H de 6 sinais com hedge (bias direcional).
        Complementares ao longo do dia: 1H swing + 1 sniper oportunístico.
        Total: ~7 sinais por dia.

        Templates: (anchor_time, spread_min, bar, mode, max_signals)
        """
        today   = date.today()
        weekday = today.weekday()  # 0=Seg … 6=Dom

        if weekday in (5, 6):  # Fim de semana — portfolio mais leve
            templates = [
                (time(9, 30),  20, "4H", "portfolio", 4),   # portfolio 4 sinais sáb/dom
                (time(15,  0), 25, "4H", "swing",     1),   # oportunidade tarde
                (time(20,  0), 20, "1H", "swing",     1),   # sniper noturno
            ]
            bonus_chance = 0.20

        elif weekday == 0:  # Segunda — portfolio de abertura de semana
            templates = [
                (time(9,  0),  15, "4H", "portfolio", 6),   # portfolio semanal completo
                (time(13, 30), 20, "1H", "swing",     1),   # 1H tarde
                (time(17,  0), 15, "4H", "swing",     1),   # 4H americano abre
                (time(21,  0), 20, "1H", "swing",     1),   # noturno
            ]
            bonus_chance = 0.30

        elif weekday in (1, 3):  # Terça/Quinta — dias de swing
            templates = [
                (time(9,  0),  15, "4H", "portfolio", 6),   # portfolio 6 sinais
                (time(14,  0), 20, "1H", "swing",     1),   # oportunidade tarde
                (time(18, 30), 20, "4H", "swing",     1),   # 4H europeu fecha
                (time(21, 30), 20, "1H", "swing",     1),   # noturno americano
            ]
            bonus_chance = 0.35

        else:  # Quarta/Sexta — dias ativos
            templates = [
                (time(9,  0),  15, "4H", "portfolio", 6),   # portfolio 6 sinais
                (time(12, 30), 20, "1H", "swing",     1),   # almoço Europa
                (time(15, 30), 15, "4H", "swing",     1),   # abertura NY
                (time(20,  0), 20, "1H", "swing",     2),   # noturno
            ]
            bonus_chance = 0.40

        missions = []
        for anchor_t, spread, bar, mode, max_sigs in templates:
            base   = datetime.combine(today, anchor_t)
            offset = random.randint(-spread // 2, spread)  # assimétrico: não adianta muito
            missions.append({
                "time":        base + timedelta(minutes=offset),
                "bar":         bar,
                "mode":        mode,
                "max_signals": max_sigs,
            })

        # Scan sniper bônus (alta probabilidade, qualquer hora)
        if random.random() < bonus_chance:
            bonus_h = random.randint(10, 21)
            bonus_m = random.randint(0, 59)
            missions.append({
                "time":        datetime.combine(today, time(bonus_h, bonus_m)),
                "bar":         "4H",
                "mode":        "swing",
                "max_signals": 1,
            })

        missions.sort(key=lambda m: m["time"])
        self._today_schedule = [m["time"] for m in missions]

        logger.info(
            f"Agenda [{['Seg','Ter','Qua','Qui','Sex','Sáb','Dom'][weekday]}] "
            f"{len(missions)} missões: "
            + ", ".join(f"{m['time'].strftime('%H:%M')}[{m['bar']}/{m['mode']}]" for m in missions)
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
        self.payment_manager.set_bot_app(self._app)  # injeta para envio de mensagens

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
