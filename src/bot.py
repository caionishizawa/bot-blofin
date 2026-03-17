"""
Bot BloFin — Main orchestrator.

Runs the trading signal scanner, sends alerts via Telegram,
tracks trades in real-time, and maintains performance records.
"""

import asyncio
import os
import sys
import logging
import yaml

from modules.scanner import scan_pairs
from modules.tracker import TradeTracker
from modules.performance import PerformanceDB
from modules.llm_analyst import analyze_signal
from modules.chart_generator import create_chart
from utils.blofin_api import BloFinAPI
from utils.formatters import format_signal_message, format_update_message, format_stats_message

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


DEFAULT_PAIRS = [
    "BTC-USDT", "ETH-USDT", "SOL-USDT", "XRP-USDT", "DOGE-USDT",
    "ADA-USDT", "AVAX-USDT", "LINK-USDT", "DOT-USDT", "MATIC-USDT",
]


def load_config(path: str = "config.yaml") -> dict:
    """Load YAML configuration file."""
    if os.path.exists(path):
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return {}


class BloFinBot:
    """Main bot orchestrator."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.tracker = TradeTracker()
        self.db = PerformanceDB(self.config.get("db_path", "data/trades.db"))
        self.api = BloFinAPI()
        self.running = False
        self._telegram_bot = None

    async def start(self):
        """Initialize and start the bot."""
        logger.info("Starting BloFin Bot...")
        await self.db.initialize()
        self.running = True

        # Run scan loop
        try:
            while self.running:
                await self._scan_cycle()
                await self._update_trades()
                interval = self.config.get("scan_interval", 3600)
                logger.info(f"Next scan in {interval}s")
                await asyncio.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        finally:
            await self.shutdown()

    async def _scan_cycle(self):
        """Run one scan cycle across all pairs."""
        pairs = self.config.get("pairs", DEFAULT_PAIRS)
        bar = self.config.get("timeframe", "1H")
        logger.info(f"Scanning {len(pairs)} pairs on {bar}...")

        signals = await scan_pairs(pairs, bar=bar)
        logger.info(f"Found {len(signals)} signals")

        for signal in signals:
            # Add to tracker
            self.tracker.add_trade(signal)

            # Generate analysis
            analysis = await analyze_signal(signal)

            # Generate chart
            chart_cfg = self.config.get("chart", {"chart": {}})
            chart_buf = create_chart(signal, {"chart": chart_cfg})

            # Format message
            ref_link = self.config.get("ref_link", "")
            msg = format_signal_message(signal, analysis=analysis, ref_link=ref_link)
            logger.info(f"Signal: {signal['pair']} {signal['direction']} (score: {signal['score']})")

    async def _update_trades(self):
        """Update prices for active trades."""
        for pair, trade in list(self.tracker.active_trades.items()):
            try:
                ticker = await self.api.get_ticker(pair)
                if ticker:
                    price = float(ticker.get("last", 0))
                    event = trade.check_levels(price)
                    if event:
                        logger.info(f"{event} on {pair} at {price}")
                        # Save to DB if trade closed
                        if event in ("SL_HIT", "TP3_HIT"):
                            await self.db.save_trade(trade.to_dict())
                            self.tracker.remove_trade(pair)
            except Exception as e:
                logger.error(f"Error updating {pair}: {e}")

    async def shutdown(self):
        """Clean shutdown."""
        self.running = False
        await self.api.close()
        await self.db.close()
        logger.info("Bot shut down")


async def main():
    config = load_config()
    bot = BloFinBot(config)
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
