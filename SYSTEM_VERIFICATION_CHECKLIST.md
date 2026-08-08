# WealthQuant V8.3 — System Verification & Deployment Checklist

**Purpose:** Executive Gatekeeping Checklist for Production Merges and Releases.  
**Rule:** Every item on this checklist MUST be marked `[x] PASS` before deploying code to production servers.

---

## 1. PRE-DEPLOYMENT GATEKEEPING CHECKLIST

### Phase A — Service Health & Connectivity
- [ ] **PostgreSQL Connectivity:** Verified connection pool on `127.0.0.1:5432` (`wealthquant` DB).
- [ ] **FastAPI Server Launch:** Server starts cleanly without syntax or import errors.
- [ ] **React Frontend Build:** Frontend compiles with 0 errors (`npm run build`).

### Phase B — Database & Data Warehouse Sanity
- [ ] **Table Count:** Exactly 25 tables present in PostgreSQL public schema.
- [ ] **Schema Migration Check:** Zero unapplied migrations; composite UNIQUE constraints active.
- [ ] **Deduplication Audit:** 0 duplicate rows in `predictions`, `prediction_history`, or `regime_history`.
- [ ] **Connection Release Audit:** 0 unreleased database connections after 1,000 requests.

### Phase C — API Endpoint & Latency Sanity
- [ ] **Root Health Endpoint:** `GET /` returns `200 OK` (`"status": "WealthQuant API running"`).
- [ ] **Dashboard Endpoint:** `GET /api/dashboard/NIFTY` returns `200 OK` in < 100ms.
- [ ] **Pipeline Endpoint:** `GET /api/pipeline/NIFTY` returns valid Stage 1–10 probabilities.
- [ ] **System Metrics Endpoint:** `GET /api/metrics` displays p50/p95 latency and cache hit ratios.

### Phase D — Prediction Locking & Mid-Candle Invariance
- [ ] **Single Candle Lock:** Consecutive calls for the same 15m candle return identical `prediction_id`.
- [ ] **Mid-Candle Invariance:** Prediction signal, regime, and probabilities do NOT mutate mid-candle.
- [ ] **Timestamp Binding:** `_candle_id` correctly binds to snapshot timestamps (`base_dt`).

### Phase E — Cache Performance & Thundering Herd Protection
- [ ] **Single-Flight Lock:** Cache misses under concurrent requests trigger exactly ONE calculation.
- [ ] **Per-Symbol Lock Isolation:** Concurrent requests for NIFTY and BANKNIFTY execute in parallel.
- [ ] **LRU Eviction:** `DashboardCache` dictionary length remains <= 500 keys under dynamic symbol load.

### Phase F — Scheduler & Background Worker Reliability
- [ ] **Market Recorder Cadence:** 30s tick recorder runs reliably without reentrant overlaps.
- [ ] **Task Error Recovery:** Background worker exceptions trigger exponential backoff retry.
- [ ] **Memory Growth Check:** Latency history deque remains bounded at 1,000 items.

### Phase G — Automated Test Suite Execution
- [ ] **Pytest Pass Rate:** 100% of automated unit, integration, and regression tests pass (`pytest backend/tests/`).
- [ ] **Zero Model Drift:** All quantitative probability outputs match golden baselines within $\epsilon = 10^{-4}$.
- [ ] **1,000-User Stress Profile:** Locust load test passes with 0% error rate and p95 latency < 500ms.

---

## 2. AUTOMATED EXECUTION COMMANDS

Run the following automated verification suite before signing off on deployment:

```bash
# 1. Run unit, integration, and prediction lock tests
pytest backend/tests/ -v

# 2. Run model regression baseline comparison
python backend/tests/test_regression_baseline.py

# 3. Run single-flight cache and DB pool sanity checks
python backend/tests/test_cache_single_flight.py
python backend/tests/test_db_pool.py

# 4. Run 100-user stress test profile
locust -f backend/tests/test_stress_locust.py --headless -u 100 -r 10 --run-time 1m --host http://localhost:8000

# 5. Run full system health & startup dashboard verification
python backend/verify_platform.py
```

---

## 3. FINAL SIGN-OFF MANDATE

> [!IMPORTANT]
> **DEPLOYMENT APPROVAL MANDATE**
> 
> Only when all 22 checklist items above are verified `[x] PASS` may the release candidate be promoted to production trading operations.
