"""
Scanner Module — scans multiple pairs for trading signals.
"""

import asyncio
from utils.blofin_api import BloFinAPI
from utils.indicators import candles_to_df, add_all_indicators, detect_signal

# Max allowed drift between candle close (entry) and current market price
MAX_ENTRY_DRIFT_PCT = 1.5


async def scan_pairs(pairs: list, bar: str = "1H", limit: int = 200, delay: float = 0.3) -> list:
    """Scan multiple pairs and return detected signals with price-aligned entries."""
    api = BloFinAPI()
    signals = []

    for pair in pairs:
        try:
            candles = await api.get_candles(pair, bar=bar, limit=limit)
            if candles:
                df = candles_to_df(candles)
                df = add_all_indicators(df)
                scalp = bar in ("1m", "3m", "5m", "15m", "30m")
                signal = detect_signal(df, scalp=scalp)
                if signal:
                    # Validate entry is close to current market price
                    try:
                        ticker = await api.get_ticker(pair)
                        current_price = float(ticker.get("last", 0))
                        if current_price > 0:
                            drift_pct = abs(current_price - signal["entry"]) / signal["entry"] * 100
                            if drift_pct > MAX_ENTRY_DRIFT_PCT:
                                print(f"Skipping {pair}: entry {signal['entry']:.2f} drifted {drift_pct:.1f}% from market {current_price:.2f}")
                                await asyncio.sleep(delay)
                                continue
                            # Use current price as entry for accuracy
                            signal["entry"] = current_price
                    except Exception:
                        pass  # Keep candle-based entry if ticker fails

                    signal["pair"] = pair
                    signal["timeframe"] = bar
                    signal["candles_df"] = df
                    signals.append(signal)
            await asyncio.sleep(delay)
        except Exception as e:
            print(f"Error scanning {pair}: {e}")

    await api.close()
    return signals
