# WealthQuant V8.3 — Institutional Test Matrix

**Document Status:** Approved Specification  
**Scope:** Complete End-to-End Test Case Definitions  

---

## 1. COMPREHENSIVE TEST MATRIX TABLE

| Test ID | Category | Component | Test Scenario | Pre-conditions | Expected Result / Target Metric | Severity |
|---|---|---|---|---|---|:---:|
| **API-01** | API | `/api/dashboard/{symbol}` | Fetch NIFTY dashboard payload | Server running | Status 200, valid schema, latency < 100ms | **P0** |
| **API-02** | API | `/api/dashboard/{symbol}` | Invalid symbol input (e.g. `INVALID`) | Server running | Status 404/400 or graceful fallback dict | **P2** |
| **API-03** | API | `/api/pipeline/{symbol}` | Execute full 10-stage AI pipeline | Server running | Status 200, contains probability distribution | **P0** |
| **API-04** | API | `/api/metrics` | Query system latency metrics | 100 API requests logged | Returns p50, p95, cache hit ratio | **P1** |
| **API-05** | API | `/api/pipeline/db-health` | Query database health diagnostic | DB connected | Status 200, total rows > 10,000 | **P1** |
| **API-06** | API | `/` | Root health check | Server running | Status 200, `"status": "WealthQuant API running"` | **P2** |
| **PRED-01**| Prediction | `PredictionStore` | Fetch live prediction twice in same 15m candle | Live server | Second call returns locked prediction with identical UUID | **P0** |
| **PRED-02**| Prediction | `PredictionStore` | Candle boundary transition | Candle crosses 15m boundary | Old prediction expires (`EXPIRED`), new prediction generated | **P0** |
| **PRED-03**| Prediction | `PredictionStore` | Snapshot timestamp binding (`base_dt`) | Historical tick playback | `candle_id` binds to snapshot timestamp, not wall-clock | **P1** |
| **PRED-04**| Prediction | `PredictionStore` | Thread-safe prediction lock | 20 concurrent tasks lock prediction | Exactly 1 prediction created; 19 lock hits | **P0** |
| **PRED-05**| Prediction | `PredictionStore` | Cold start metadata synthesis | DB contains historical prediction | Synthesizes `prediction_meta` from PostgreSQL | **P2** |
| **DB-01**  | Database | `pipeline_db` | Connection pool checkout under load | 50 concurrent DB queries | Connections checked out and released without pool leak | **P0** |
| **DB-02**  | Database | `predictions` | Duplicate insert attempt | Duplicate prediction UUID inserted | Handled by `ON CONFLICT DO UPDATE` without exception | **P0** |
| **DB-03**  | Database | PostgreSQL | Query latency audit | Execute `_fetch_dashboard_db_metadata` | Total execution time < 5ms for combined query | **P1** |
| **DB-04**  | Database | `ohlcv_history` | Foreign key & schema verification | DB initialized | All 25 tables present with composite indexes | **P1** |
| **DB-05**  | Database | `pipeline_db` | Connection pool shutdown safety | Lifespan shutdown | Connection pool closes cleanly on server stop | **P2** |
| **SCHED-01**| Scheduler | `wq_scheduler` | Market Recorder cadence check | Market hours active | Fires tick recorder every 30s (+/- 0.5s precision) | **P1** |
| **SCHED-02**| Scheduler | `wq_scheduler` | Non-reentrancy verification | Long-running task active | Prevents overlap; skips cycle if previous tick incomplete | **P0** |
| **SCHED-03**| Scheduler | `_SchedulerState` | Latency list memory cap | 5,000 recorder ticks | `recorder_latencies` stays capped at 1,000 items | **P2** |
| **SCHED-04**| Scheduler | `wq_scheduler` | Daily close evaluator | Time reaches 15:35 IST | Triggers `DAILY_PLATFORM_REPORT.md` generation | **P2** |
| **CACHE-01**| Cache | `cache.py` | Single-Flight lock on cache miss | 50 concurrent requests for cold key | Exactly 1 computation executed; 49 wait and hit cache | **P0** |
| **CACHE-02**| Cache | `cache.py` | Per-Symbol YF Lock isolation | Concurrent fetch NIFTY + BANKNIFTY | Fetches run in parallel without blocking each other | **P1** |
| **CACHE-03**| Cache | `DashboardCache` | Maximum capacity eviction | Insert 550 distinct symbols | Size capped at 500; oldest/expired entry evicted | **P2** |
| **CACHE-04**| Cache | `cache.py` | TTL expiration | Wait 61s on 60s TTL key | Key automatically invalidated; next call fetches fresh | **P1** |
| **PERF-01**| Performance| Server | Cold start startup time | Server boot | Uvicorn binds and pre-warms in < 5.0 seconds | **P1** |
| **PERF-02**| Performance| Server | Dashboard Cache Hit latency | Warm cache | Response time < 5.0 ms | **P0** |
| **PERF-03**| Performance| Server | Dashboard Cache Miss latency | Cold cache | Response time < 100.0 ms | **P1** |
| **PERF-04**| Performance| Pipeline | 15m Signal Execution latency | Full pipeline run | Total latency < 200.0 ms | **P0** |
| **PERF-05**| Performance| Memory | RSS memory footprint | 24-hour continuous run | RAM usage growth < 50 MB over 24h | **P1** |
| **REG-01** | Regression | Hawkes Model | Intensity output regression | Test vector input | Output matches golden baseline within 0.0001 | **P0** |
| **REG-02** | Regression | Kalman Filter | State estimation regression | Test vector input | Output matches golden baseline within 0.0001 | **P0** |
| **REG-03** | Regression | Bayesian Fusion| Model agreement ratio | Test vector input | Dominant model and signal match baseline | **P0** |
| **STR-01** | Stress | Server | 100 Virtual Users load profile | Locust 5-min run | 0% error rate, p95 latency < 150ms | **P1** |
| **STR-02** | Stress | Server | 500 Virtual Users load profile | Locust 5-min run | 0% error rate, p95 latency < 300ms | **P1** |
| **STR-03** | Stress | Server | 1,000 Virtual Users load profile| Locust 5-min run | Error rate < 0.1%, p95 latency < 500ms | **P0** |
| **REC-01** | Recovery | PostgreSQL | Database disconnection self-healing | Kill PG process | System falls back to CSV, reconnects when PG restarts | **P0** |
| **REC-02** | Recovery | FastAPI | Worker restart recovery | Kill Uvicorn worker | State recovered from DB without data corruption | **P1** |
| **REC-03** | Recovery | NSE API | Timeout / Rate limit recovery | Simulate NSE 429 | Fail-fast policy caches offline status for 120s | **P1** |

---

## 2. SEVERITY LEVEL CLASSIFICATION

- **P0 (Critical / Blocker):** Issues that cause server crashes, corrupted predictions, DB connection pool leaks, or prediction shifts mid-candle. Must be fixed immediately.
- **P1 (High):** Performance degradations exceeding target latency bounds (>500ms), single-thread lock bottlenecks, or high load errors. Must be fixed before staging.
- **P2 (Medium):** Memory growth over 24h, static directory clutter, or minor schema warnings. Addressed in normal sprint cycle.
- **P3 (Low):** Micro-optimizations and code documentation hygiene.
