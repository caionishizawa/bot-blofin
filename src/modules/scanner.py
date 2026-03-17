"""
Scanner Module — scans multiple pairs for trading signals.
"""

import asyncio
from utils.blofin_api import BloFinAPI
from utils.indicators import candles_to_df, add_all_indicators, detect_signal


async def scan_pairs(pairs: list, bar: str = "1H", limit: int = 200, delay: float = 0.3) -> list:
    """Scan multiple pairs and return detected signals."""
    api = BloFinAPI()
    signals = []

    for pair in pairs:
        try:
            candles = await api.get_candles(pair, bar=bar, limit=limit)
            if candles:
                df = candles_to_df(candles)
                df = add_all_indicators(df)
                signal = detect_signal(df)
                if signal:
                    signal["pair"] = pair
                    signal["timeframe"] = bar
                    signal["candles_df"] = df
                    signals.append(signal)
            await asyncio.sleep(delay)
        except Exception as e:
            print(f"Error scanning {pair}: {e}")

    await api.close()
    return signals
