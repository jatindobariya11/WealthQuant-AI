import os
from concurrent.futures import ThreadPoolExecutor

import requests

from core.shared_features import *

_EXECUTOR = ThreadPoolExecutor(max_workers=8)

BREEZE_API_KEY = os.getenv("BREEZE_API_KEY", "")  # from ICICI

BREEZE_API_SECRET = os.getenv("BREEZE_API_SECRET", "")

BREEZE_SESSION = os.getenv("BREEZE_SESSION_TOKEN", "")  # from login

TRUEDATA_USER = os.getenv("TRUEDATA_USER", "")  # from TrueData

TRUEDATA_PASSWORD = os.getenv("TRUEDATA_PASSWORD", "")

YFINANCE_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "FINNIFTY": "NIFTY_FIN_SERVICE.NS",
    "MIDCPNIFTY": "NIFTY_MID_SELECT.NS",
    "SENSEX": "^BSESN",
}

NSE_INDEX_MAP = {
    "NIFTY": "NIFTY 50",
    "BANKNIFTY": "NIFTY BANK",
    "FINNIFTY": "NIFTY FIN SERVICE",
    "MIDCPNIFTY": "NIFTY MIDCAP SELECT",
    "SENSEX": "SENSEX",
}

INTERVAL_MAP = {
    # yfinance interval → (yf_interval, yf_period)
    "1m": ("1m", "5d"),
    "5m": ("5m", "5d"),
    "15m": ("15m", "5d"),
    "30m": ("30m", "1mo"),
    "1h": ("1h", "1mo"),
    "1d": ("1d", "1y"),
}

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

SESSION_REFRESH_SEC = 600  # refresh session every 10 minutes

BREEZE_STOCK_CODE = {
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNI",
    "FINNIFTY": "FINNIF",
    "MIDCPNIFTY": "MIDCPN",
    "SENSEX": "SENSEX",
}

BREEZE_INTERVAL = {
    "1m": "1minute",
    "5m": "5minute",
    "15m": "15minute",
    "30m": "30minute",
    "1h": "1hour",
    "1d": "1day",
}

TRUEDATA_SYMBOL_MAP = {
    "NIFTY": "NIFTY-I",
    "BANKNIFTY": "BANKNIFTY-I",
    "FINNIFTY": "FINNIFTY-I",
    "SENSEX": "SENSEX-I",
}

TRUEDATA_INTERVAL_MAP = {
    "1m": "1",
    "5m": "5",
    "15m": "15",
    "30m": "30",
    "1h": "60",
    "1d": "1D",
}

NSE_SESSION = requests.Session()

FII_CACHE = os.path.join(os.path.dirname(__file__), "fii_cache.json")  # FIX #3

_GLOBAL_SYMS = {
    "Dow Futures": "YM=F",
    "Nasdaq Futures": "NQ=F",
    "S&P 500 Futures": "ES=F",
    "Dollar Index": "DX-Y.NYB",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "Crude Oil": "CL=F",
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^IXIC",
    "Dow Jones": "^DJI",
    "KOSPI": "^KS11",
    "DAX": "^GDAXI",
    "FTSE 100": "^FTSE",
    "Brent Crude": "BZ=F",
    "USD/INR": "INR=X",
    "Spot Gold": "GC=F",
}
