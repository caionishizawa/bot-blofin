"""
Bot BloFin — Orquestrador principal com integração Telegram completa.

Uso:
    cd src && python bot.py
"""

import asyncio
import logging
import os

import yaml
from dotenv import load_dotenv
from telegram import Bot, Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

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
            "📈 /stats — Performance (30 dias)\n"
            "📊 /pnl — Gráfico de equity curve\n"
            "⏹ /stop — Pausar scans automáticos\n"
            "▶️ /resume — Retomar scans\n",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_scan(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        msg = await update.message.reply_text("🔍 Escaneando pares...")
        count = await self._scan_cycle()
        await msg.edit_text(f"✅ Scan concluído — {count} sinal(is) encontrado(s).")

    async def cmd_trades(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        trades = self.tracker.get_all()
        text = format_trades_list(trades)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_stats(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        stats = await self.db.get_stats()
        text = format_stats_message(stats)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

    async def cmd_pnl(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        trades = await self.db.get_recent_trades(limit=50)
        if not trades:
            await update.message.reply_text("📭 Nenhum trade registrado ainda.")
            return
        buf = create_pnl_chart(trades, self.config)
        await update.message.reply_photo(photo=buf, caption="📊 *Equity Curve — NPK Sinais*", parse_mode=ParseMode.MARKDOWN)

    async def cmd_stop(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = False
        await update.message.reply_text("⏹ Scans automáticos pausados.")

    async def cmd_resume(self, update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        self.running = True
        await update.message.reply_text("▶️ Scans automáticos retomados.")

    # ------------------------------------------------------------------
    # Lógica principal
    # ------------------------------------------------------------------

    async def _scan_cycle(self) -> int:
        """Escaneia todos os pares e envia sinais ao canal. Retorna nº de sinais."""
        pairs = self.config.get("pairs", DEFAULT_PAIRS)
        bar = self.config.get("timeframe", "1H")
        min_rr = self.config.get("min_rr", 1.5)
        max_rr = self.config.get("max_rr", 4.0)
        min_confidence = self.config.get("min_confidence", 50)

        logger.info(f"Escaneando {len(pairs)} pares em {bar}...")
        signals = await scan_pairs(pairs, bar=bar)
        logger.info(f"{len(signals)} sinal(is) bruto(s) encontrado(s)")

        # Filter by quality
        filtered = [
            s for s in signals
            if s.get("rr_ratio", 0) >= min_rr
            and s.get("rr_ratio", 0) <= max_rr
            and s.get("confidence", 0) >= min_confidence
        ]
        logger.info(f"{len(filtered)} sinal(is) após filtro (RR {min_rr}-{max_rr}, conf ≥{min_confidence}%)")

        for signal in filtered:
            # Register in tracker
            self.tracker.add_trade(signal)

            # Claude AI analysis
            analysis = await analyze_signal(signal)

            # Generate chart
            chart_buf = create_chart(signal, self.config)

            # Format message
            msg = format_signal_message(signal, analysis=analysis, ref_link=self.ref_link)

            logger.info(
                f"Sinal: {signal['pair']} {signal['direction']} "
                f"conf={signal.get('confidence')}% rr={signal.get('rr_ratio')}"
            )
            await self._send(msg, photo=chart_buf)

        return len(filtered)

    async def _update_trades(self):
        """Verifica SL/TP nos trades ativos."""
        for pair, trade in list(self.tracker.active_trades.items()):
            try:
                ticker = await self.api.get_ticker(pair)
                if not ticker:
                    continue
                price = float(ticker.get("last", 0))
                event = trade.check_levels(price)
                if event:
                    trade_dict = trade.to_dict()
                    logger.info(f"{event} em {pair} @ {price} | PNL: {trade_dict['pnl_pct']:+.2f}%")
                    msg = format_update_message(pair, event, trade_dict)
                    await self._send(msg)

                    # Save to DB on close (SL or TP3), save on any TP for partial tracking
                    await self.db.save_trade(trade_dict)

                    # Remove from active only on final events
                    if event in ("SL_HIT", "TP3_HIT"):
                        self.tracker.remove_trade(pair)

            except Exception as e:
                logger.error(f"Erro atualizando {pair}: {e}")

    async def _background_loop(self):
        """Loop de background: scan periódico + atualização de trades."""
        interval = self.config.get("scan_interval", 3600)
        update_interval = self.config.get("update_interval", 60)
        logger.info(f"Background loop iniciado (scan: {interval}s, update: {update_interval}s)")

        scan_counter = 0
        while True:
            try:
                if self.running:
                    # Update active trades every tick
                    await self._update_trades()

                    # Run full scan every N ticks
                    scan_counter += 1
                    if scan_counter >= (interval // update_interval):
                        scan_counter = 0
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

        self._app = Application.builder().token(self.token).build()

        self._app.add_handler(CommandHandler("start", self.cmd_start))
        self._app.add_handler(CommandHandler("scan", self.cmd_scan))
        self._app.add_handler(CommandHandler("trades", self.cmd_trades))
        self._app.add_handler(CommandHandler("stats", self.cmd_stats))
        self._app.add_handler(CommandHandler("pnl", self.cmd_pnl))
        self._app.add_handler(CommandHandler("stop", self.cmd_stop))
        self._app.add_handler(CommandHandler("resume", self.cmd_resume))

        logger.info("Bot iniciando...")

        async with self._app:
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)

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
