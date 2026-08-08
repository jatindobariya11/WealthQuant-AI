"""
cache.py — Lightweight in-memory cache with configurable TTL.
Thread-safe, zero dependencies. Used by all data-fetching modules
to eliminate redundant Yahoo Finance / NSE / NewsAPI calls.

Includes Single-Flight Locking (thundering herd protection) and
Per-Symbol Lock isolation for yfinance fetches.
"""

import collections
import threading
import time
from functools import wraps

_store = {}  # { key: (value, expire_ts) }
_lock = threading.Lock()

# ── Single-Flight Key Locks (Thundering Herd Protection) ───────────────────
_key_locks = collections.OrderedDict()
_key_locks_mutex = threading.Lock()


def _get_key_lock(key: str) -> threading.Lock:
    with _key_locks_mutex:
        if key not in _key_locks:
            if len(_key_locks) >= 500:
                _key_locks.popitem(last=False)
            _key_locks[key] = threading.Lock()
        else:
            _key_locks.move_to_end(key)
        return _key_locks[key]


# ── Per-Symbol YF Locks (Replaces global YF_LOCK contention) ──────────────
YF_LOCK = threading.Lock()  # Retained for legacy backward compatibility
_symbol_yf_locks = collections.OrderedDict()
_symbol_yf_mutex = threading.Lock()


def get_symbol_yf_lock(symbol: str) -> threading.Lock:
    """Returns a symbol-specific lock so different symbols download concurrently."""
    sym = (symbol or "DEFAULT").upper()
    with _symbol_yf_mutex:
        if sym not in _symbol_yf_locks:
            if len(_symbol_yf_locks) >= 500:
                _symbol_yf_locks.popitem(last=False)
            _symbol_yf_locks[sym] = threading.Lock()
        else:
            _symbol_yf_locks.move_to_end(sym)
        return _symbol_yf_locks[sym]


# ── TTL presets (seconds) ──────────────────────────────────
TTL_VIX = 60  # VIX moves slowly
TTL_GLOBAL = 60  # Futures refresh ~1 min
TTL_FII = 900  # FII/DII: once-daily data, 15 min cache
TTL_NEWS = 300  # 5 min for news
TTL_OPTIONS = 120  # 2 min for options chain
TTL_SIGNALDESK = 60  # Main signal: 60 s
TTL_SCREENER = 300  # Full Nifty50 scan: 5 min
TTL_ADV_DEC = 900  # 15 min
TTL_MULTI_TF = 60  # Multi-timeframe: 1 min
TTL_QUANT = 60  # Quant engine: 1 min
TTL_LTP = 10  # Live price: 10 s
TTL_INSTITUTIONAL = 30  # Institutional flow: 30 s


def get(key):
    """Return cached value or None if expired / missing."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expire_ts = entry
        if time.time() > expire_ts:
            del _store[key]
            return None
        return value


def put(key, value, ttl):
    """Store value with TTL (seconds from now)."""
    with _lock:
        if len(_store) >= 1000:
            now = time.time()
            to_del = [k for k, (v, exp) in _store.items() if now > exp]
            for k in to_del:
                _store.pop(k, None)
            if len(_store) >= 1000:
                oldest = min(_store.keys(), key=lambda k: _store[k][1])
                _store.pop(oldest, None)
        _store[key] = (value, time.time() + ttl)


def invalidate(key=None):
    """Clear one key or everything."""
    with _lock:
        if key:
            _store.pop(key, None)
        else:
            _store.clear()


def status():
    """Return cache statistics for diagnostics."""
    with _lock:
        now = time.time()
        total = len(_store)
        alive = sum(1 for _, (__, exp) in _store.items() if exp > now)
        expired = total - alive
        entries = {}
        for k, (_, exp) in _store.items():
            remaining = max(0, round(exp - now, 1))
            entries[k] = {"ttl_remaining": remaining, "alive": exp > now}
        return {
            "total_keys": total,
            "alive": alive,
            "expired": expired,
            "entries": entries,
        }


def cached(key_fn, ttl):
    """
    Decorator with Single-Flight Thundering Herd Protection.
    Guarantees only ONE thread runs the calculation on a cache miss,
    while concurrent threads wait for the computed result.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs)
            hit = get(k)
            if hit is not None:
                return hit

            # Cache miss: acquire per-key single-flight lock
            key_lock = _get_key_lock(k)
            with key_lock:
                # Re-check cache after acquiring lock
                hit = get(k)
                if hit is not None:
                    return hit
                result = fn(*args, **kwargs)
                put(k, result, ttl)
                return result

        wrapper._cache_key_fn = key_fn
        return wrapper

    return decorator
