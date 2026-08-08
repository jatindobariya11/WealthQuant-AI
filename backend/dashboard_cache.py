"""
╔══════════════════════════════════════════════════════════════════════════╗
║  WealthQuant — DashboardCache                                            ║
║                                                                          ║
║  MISSION: In-memory dashboard state cache.                               ║
║                                                                          ║
║  Rules:                                                                  ║
║    - Store latest dashboard state per symbol in memory                   ║
║    - Refresh only when new candle closes OR market snapshot updates      ║
║    - Frontend reads from cache → zero repeated PostgreSQL queries        ║
║    - Hard TTL: 60s regardless                                            ║
║    - Thread-safe                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

import logging
import threading
import time

logger = logging.getLogger("wealthquant.dashboard_cache")

# Hard TTL for dashboard cache (seconds)
DASHBOARD_CACHE_TTL = 60.0
# Minimum LTP change (%) to trigger a refresh
LTP_CHANGE_THRESHOLD_PCT = 0.01


class _DashboardEntry:
    """One cached dashboard state for a symbol."""

    __slots__ = ("data", "stored_at", "candle_ts", "ltp", "symbol")

    def __init__(self, symbol: str, data: dict, candle_ts: str, ltp: float):
        self.symbol = symbol
        self.data = data
        self.stored_at = time.monotonic()
        self.candle_ts = candle_ts  # Last candle timestamp string
        self.ltp = ltp  # Last price when cached

    def is_expired(self) -> bool:
        return (time.monotonic() - self.stored_at) > DASHBOARD_CACHE_TTL

    def age_seconds(self) -> float:
        return round(time.monotonic() - self.stored_at, 1)


class DashboardCache:
    """
    Per-symbol in-memory dashboard cache.

    Refresh triggers:
      1. candle_ts changes (new candle closed)
      2. LTP moves by > LTP_CHANGE_THRESHOLD_PCT
      3. Hard TTL (60s) expires
    """

    MAX_CAPACITY = 500

    def __init__(self):
        self._store: dict[str, _DashboardEntry] = {}
        self._lock = threading.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "refresh_candle": 0,
            "refresh_ltp": 0,
            "refresh_ttl": 0,
        }

    def get(self, symbol: str) -> dict | None:
        """Return cached dashboard data, or None if stale/missing."""
        key = symbol.upper()
        with self._lock:
            entry = self._store.get(key)
            if entry and not entry.is_expired():
                self._stats["hits"] += 1
                # Inject cache metadata into a copy
                result = dict(entry.data)
                result["_cache"] = {
                    "hit": True,
                    "age_seconds": entry.age_seconds(),
                    "candle_ts": entry.candle_ts,
                }
                return result
            self._stats["misses"] += 1
            return None

    def set(self, symbol: str, data: dict, candle_ts: str = "", ltp: float = 0.0):
        """Store dashboard data for a symbol."""
        key = symbol.upper()
        entry = _DashboardEntry(symbol, data, candle_ts, ltp)
        with self._lock:
            if len(self._store) >= self.MAX_CAPACITY:
                # Evict expired entries first
                to_del = [k for k, e in self._store.items() if e.is_expired()]
                for k in to_del:
                    self._store.pop(k, None)
                # If still at capacity, evict oldest entry
                if len(self._store) >= self.MAX_CAPACITY:
                    oldest = min(
                        self._store.keys(), key=lambda k: self._store[k].stored_at
                    )
                    self._store.pop(oldest, None)
            self._store[key] = entry
        logger.debug(
            f"[DashboardCache] Stored {symbol} | candle={candle_ts} | ltp={ltp}"
        )

    def should_refresh(self, symbol: str, new_candle_ts: str, new_ltp: float) -> bool:
        """
        Decide whether dashboard data needs to be refreshed.
        Returns True if:
          - No cached entry
          - Hard TTL expired
          - New candle has closed (candle_ts changed)
          - LTP moved by > threshold
        """
        key = symbol.upper()
        with self._lock:
            entry = self._store.get(key)

            if not entry:
                return True

            if entry.is_expired():
                self._stats["refresh_ttl"] += 1
                return True

            if new_candle_ts and entry.candle_ts != new_candle_ts:
                self._stats["refresh_candle"] += 1
                logger.info(
                    f"[DashboardCache] {symbol} — new candle {new_candle_ts}, refreshing."
                )
                return True

            if new_ltp > 0 and entry.ltp > 0:
                pct_change = abs(new_ltp - entry.ltp) / entry.ltp * 100
                if pct_change > LTP_CHANGE_THRESHOLD_PCT:
                    self._stats["refresh_ltp"] += 1
                    return True

        return False

    def invalidate(self, symbol: str | None = None):
        """Force-invalidate one symbol or all."""
        with self._lock:
            if symbol:
                self._store.pop(symbol.upper(), None)
            else:
                self._store.clear()
        logger.info(f"[DashboardCache] Invalidated: {symbol or 'ALL'}")

    def stats(self) -> dict:
        """Return cache health statistics."""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_ratio = round(self._stats["hits"] / total, 4) if total > 0 else 0.0
            symbols = {
                sym: {
                    "age_seconds": entry.age_seconds(),
                    "candle_ts": entry.candle_ts,
                    "ltp": entry.ltp,
                    "expired": entry.is_expired(),
                }
                for sym, entry in self._store.items()
            }
            return {
                **self._stats,
                "hit_ratio": hit_ratio,
                "total_requests": total,
                "symbols": symbols,
            }


# ── Singleton ─────────────────────────────────────────────────────────────
dashboard_cache = DashboardCache()
