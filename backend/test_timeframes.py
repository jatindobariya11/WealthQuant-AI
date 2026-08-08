import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import get_all_data

symbol = "NIFTY"
intervals = ["1m", "5m", "15m", "30m", "1h", "1d"]

print(f"Testing all timeframes for {symbol}...\n")

for interval in intervals:
    try:
        print(f"--- Fetching {interval} ---")
        res = get_all_data(symbol, interval)
        meta = res.get("meta", {})
        ltp = res.get("ltp")
        candles = res.get("candles", [])
        mo = res.get("market_overview", {})

        print(f"LTP: {ltp}")
        print(f"Candles count: {len(candles)}")
        if candles:
            print(f"Last candle date: {candles[-1].get('Datetime')}")
        print(f"RSI: {mo.get('rsi')}")
        print(f"MACD: {mo.get('macd')}")

        # Check global and others just once or generally
        global_data = res.get("global")
        opts = res.get("options")
        print(f"Global Data Present: {bool(global_data)}")
        print(f"Options Data: {opts if isinstance(opts, str) else 'Dict present'}")
        print("\n")
    except Exception as e:
        print(f"Error for {interval}: {e}\n")
