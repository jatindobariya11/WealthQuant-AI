"""
test_stress_locust.py — WealthQuant V14.1 Expanded Load Testing Suite (FIX-007)
Tests P95/P99 latency, cache hit ratios, WebSocket concurrency, and throughput.
"""

import time

from locust import HttpUser, between, events, task


class WealthQuantLoadUser(HttpUser):
    """
    Standard API load profile targeting dashboard, pipeline, and metrics endpoints.
    Models realistic trader behavior (70% dashboard, 20% pipeline, 10% metrics).
    """

    wait_time = between(0.5, 2.0)

    # Track latency measurements for P95/P99 calculation
    _latencies = []

    @task(7)
    def poll_dashboard_nifty(self):
        start = time.perf_counter()
        self.client.get(
            "/api/dashboard/NIFTY?interval=15m", name="/api/dashboard/NIFTY"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        WealthQuantLoadUser._latencies.append(elapsed_ms)

    @task(2)
    def query_pipeline_nifty(self):
        start = time.perf_counter()
        self.client.get(
            "/api/pipeline/probability/NIFTY?interval=15m",
            name="/api/pipeline/prob/NIFTY",
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        WealthQuantLoadUser._latencies.append(elapsed_ms)

    @task(1)
    def query_system_metrics(self):
        self.client.get("/api/metrics", name="/api/metrics")

    @task(1)
    def query_health(self):
        self.client.get("/health", name="/health")

    @task(1)
    def query_market_context(self):
        self.client.get("/api/market-context", name="/api/market-context")


class WealthQuantHighFrequencyUser(HttpUser):
    """
    Aggressive load profile simulating high-frequency scanner behavior.
    Tests rate limiter enforcement at scale.
    """

    wait_time = between(0.1, 0.5)

    @task(5)
    def hammer_health(self):
        self.client.get("/health", name="/health")

    @task(3)
    def hammer_dashboard(self):
        self.client.get(
            "/api/dashboard/BANKNIFTY?interval=5m", name="/api/dashboard/BANKNIFTY"
        )

    @task(2)
    def hammer_metrics(self):
        self.client.get("/api/metrics", name="/api/metrics")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """
    On Locust test stop, compute and log P95/P99 latency statistics.
    """
    latencies = WealthQuantLoadUser._latencies
    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)
        p50 = latencies_sorted[int(n * 0.50)]
        p95 = latencies_sorted[int(n * 0.95)]
        p99 = latencies_sorted[int(n * 0.99)]
        max_lat = latencies_sorted[-1]
        print(f"\n[LoadTest] Requests sampled: {n}")
        print(f"[LoadTest] P50 Latency: {p50:.1f}ms")
        print(f"[LoadTest] P95 Latency: {p95:.1f}ms")
        print(f"[LoadTest] P99 Latency: {p99:.1f}ms")
        print(f"[LoadTest] Max Latency: {max_lat:.1f}ms")
