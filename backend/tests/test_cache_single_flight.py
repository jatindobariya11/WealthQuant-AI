"""
test_cache_single_flight.py — Pillar 5: Single-Flight Cache & Thundering Herd Protection Tests
"""

import threading
import time

import cache
from dashboard_cache import dashboard_cache


def test_cache_get_put_ttl():
    """Verify basic get/put/ttl operations in cache.py."""
    cache.put("test_key", "hello_world", ttl=10)
    assert cache.get("test_key") == "hello_world"
    cache.invalidate("test_key")
    assert cache.get("test_key") is None


def test_thundering_herd_single_flight():
    """Verify @cached decorator executes function exactly ONCE for 50 concurrent callers."""
    execution_count = 0
    exec_lock = threading.Lock()

    @cache.cached(lambda s: f"single_flight_test:{s}", ttl=60)
    def expensive_computation(symbol: str):
        nonlocal execution_count
        with exec_lock:
            execution_count += 1
        time.sleep(0.1)
        return f"result_for_{symbol}"

    def worker():
        return expensive_computation("NIFTY")

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert execution_count == 1
    assert cache.get("single_flight_test:NIFTY") == "result_for_NIFTY"


def test_per_symbol_yf_lock_isolation():
    """Verify get_symbol_yf_lock produces distinct locks for distinct symbols."""
    lock_nifty = cache.get_symbol_yf_lock("NIFTY")
    lock_bnf = cache.get_symbol_yf_lock("BANKNIFTY")
    assert lock_nifty is not lock_bnf


def test_dashboard_cache_capacity_eviction():
    """Verify DashboardCache caps entries at MAX_CAPACITY=500."""
    dashboard_cache.invalidate()
    for i in range(550):
        dashboard_cache.set(f"SYM_{i}", {"price": i}, candle_ts="15m", ltp=100.0)

    stats = dashboard_cache.stats()
    assert len(stats["symbols"]) <= 500
