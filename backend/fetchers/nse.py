import time

import requests

from core.shared_features import *

from .config import *


def _get_session(force: bool = False) -> requests.Session:
    """Return a warmed-up NSE session. Auto-refreshes every 10 min."""
    global _session, _session_ts

    # Fast path without lock
    if _session and not force and (time.time() - _session_ts < SESSION_REFRESH_SEC):
        return _session

    with _session_lock:
        # Double check inside lock
        if _session and not force and (time.time() - _session_ts < SESSION_REFRESH_SEC):
            return _session

        s = requests.Session()
        s.headers.update(NSE_HEADERS)

        # Warmup — NSE requires hitting the homepage first to get cookies
        try:
            s.get("https://www.nseindia.com", timeout=10)
            time.sleep(1.5)
            s.get("https://www.nseindia.com/market-data/live-equity-market", timeout=10)
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"NSE warmup failed: {e}")

        _session = s
        _session_ts = time.time()
        return s


def reset_nse_session():
    """Call this if you get a 403. Forces a fresh session + warmup."""
    global _session, _session_ts
    with _session_lock:
        _session = None
        _session_ts = 0
    logger.info("NSE session reset. Warming up...")
    return _get_session(force=True)


def _nse_get(url: str, retries: int = 2) -> dict:
    """GET an NSE API URL with auto-retry on 403."""
    for attempt in range(retries + 1):
        try:
            s = _get_session()
            r = s.get(url, timeout=12)
            if r.status_code == 403:
                logger.warning(
                    f"NSE 403 on attempt {attempt + 1}, refreshing session..."
                )
                reset_nse_session()
                time.sleep(2)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.JSONDecodeError:
            raise ValueError(f"NSE returned non-JSON response for {url}")
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2)
    return {}
