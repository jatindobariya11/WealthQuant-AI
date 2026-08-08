# WealthQuant V8.3 — Performance & Load Test Plan

**Purpose:** Define latency targets, throughput benchmarks, memory caps, and load testing protocols for 100, 500, and 1,000 concurrent user sessions.  

---

## 1. PERFORMANCE BENCHMARK TARGETS

| Benchmark Metric | Target Threshold | Maximum Allowed Limit | Evaluation Component |
|---|:---:|:---:|---|
| **Cold Start Boot Time** | **< 3.0 s** | **< 5.0 s** | FastAPI Lifespan + DB Pool Init |
| **Warm Start Boot Time** | **< 1.0 s** | **< 2.0 s** | Process reload |
| **Dashboard Cache Hit Latency** | **< 2.0 ms** | **< 5.0 ms** | `GET /api/dashboard/{symbol}` |
| **Dashboard Cache Miss Latency** | **< 50.0 ms** | **< 100.0 ms** | Cold DB metadata query |
| **15m Signal Pipeline Latency** | **< 150.0 ms** | **< 200.0 ms** | Stages 1–10 orchestrator run |
| **PostgreSQL Single-Query Latency** | **< 2.0 ms** | **< 5.0 ms** | Consolidated DB query |
| **RSS Memory Footprint (24h)** | **< 150 MB** | **< 250 MB** | Python Backend Process |

---

## 2. HIGH-CONCURRENCY LOAD PROFILES (LOCUST)

### Profile A: 100 Concurrent Virtual Users (Normal Market Load)
- **Ramp-up Rate:** 10 users/sec
- **Test Duration:** 5 minutes
- **Traffic Split:** 70% Dashboard Polling (`/api/dashboard/NIFTY`), 20% Pipeline Queries (`/api/pipeline/NIFTY`), 10% System Health (`/api/metrics`).
- **Target Result:** 0% Error Rate, Average Latency < 20ms, p95 Latency < 100ms.

### Profile B: 500 Concurrent Virtual Users (High Volatility Spikes)
- **Ramp-up Rate:** 25 users/sec
- **Test Duration:** 5 minutes
- **Traffic Split:** 80% Dashboard Polling, 15% Pipeline Queries, 5% Market Context.
- **Target Result:** 0% Error Rate, Average Latency < 50ms, p95 Latency < 250ms.

### Profile C: 1,000 Concurrent Virtual Users (Extreme Institutional Load)
- **Ramp-up Rate:** 50 users/sec
- **Test Duration:** 10 minutes
- **Traffic Split:** 85% Dashboard Polling, 10% Pipeline Queries, 5% System Health.
- **Target Result:** Error Rate < 0.1%, Average Latency < 100ms, p95 Latency < 500ms.

---

## 3. LOCUST LOAD SCRIPT SPECIFICATION

```python
# F:\ai-stock-platform\backend\tests\test_stress_locust.py
from locust import HttpUser, task, between

class WealthQuantUser(HttpUser):
    wait_time = between(1.0, 3.0)

    @task(7)
    def get_dashboard(self):
        self.client.get("/api/dashboard/NIFTY?interval=15m", name="/api/dashboard/NIFTY")

    @task(2)
    def get_pipeline(self):
        self.client.get("/api/pipeline/NIFTY?interval=15m", name="/api/pipeline/NIFTY")

    @task(1)
    def get_metrics(self):
        self.client.get("/api/metrics", name="/api/metrics")
```

---

## 4. RESOURCE PROFILING & HARDWARE MONITORING

During load tests, system performance is continuously logged using `psutil`:
- **CPU Utilization:** Must remain < 70% average under 500 users.
- **RAM Footprint:** Must remain flat with 0 memory leaks over 10,000 requests.
- **Asyncpg Connection Pool:** Active connections must remain <= 8 (never hitting 10 cap).
