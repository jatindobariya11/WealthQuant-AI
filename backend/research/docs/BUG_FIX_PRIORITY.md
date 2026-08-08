# WealthQuant V10.1 — Bug Fix Priority Matrix

**Audit Date:** July 24, 2026  
**Status:** Audit Complete — Waiting for User Approval to Execute Fixes

---

## Complete Priority Backlog (P0 to P3)

### Priority P0 (Critical / Immediate Fix Required)

| Bug ID | Title | Component | File / Function | Risk |
|:---:|:---|:---|:---|:---|
| **P0-1** | PredictionStore lock dictionary thread-safety | Pipeline | `backend/pipeline/prediction_store.py` :: `lock_prediction()` | Concurrent write race condition under parallel fast signals |

---

### Priority P1 (High Priority / Pre-Production Requirement)

| Bug ID | Title | Component | File / Function | Risk |
|:---:|:---|:---|:---|:---|
| **P1-1** | Dashboard Route Polling Re-computation | Backend API | `backend/dashboard_routes.py` :: `get_dashboard_summary()` | CPU spike & 180ms latency under 5s dashboard polling |
| **P1-2** | React Component Fetch Abort Missing | Frontend | `frontend/src/pages/Dashboard.js` :: `useEffect()` | Memory leak & unmounted component state updates |
| **P1-3** | Scheduler Job Execution Overlap Guard | Scheduler | `backend/pipeline/scheduler.py` :: `_collect_options_job()` | Concurrent job invocation during exchange latency spikes |
| **P1-4** | Missing Composite Index on OHLCV History | Database | PostgreSQL :: `ohlcv_history(symbol, interval, timestamp DESC)` | Slow query execution on large datasets |

---

### Priority P2 (Medium Priority / Maintenance & Optimization)

| Bug ID | Title | Component | File / Function | Risk |
|:---:|:---|:---|:---|:---|
| **P2-1** | Dual Module Redundancy (`data_fetcher` vs `data_fetchers`) | Backend | `backend/data_fetchers.py` | Double HTTP requests to exchange cookie endpoints |
| **P2-2** | Exception Detail Leakage in 500 Responses | Security | `backend/main.py` :: `global_exception_handler()` | Stack trace information exposure |
| **P2-3** | Un-memoized Option Chain Table Rendering | Frontend | `frontend/src/components/OptionsChainTable.js` | Sub-60 FPS UI frame drops during high tick volatility |
| **P2-4** | Static AsyncPG Max Connections Pool Limit | Database | `backend/pipeline/config.py` :: `POSTGRES_CONFIG` | Connection pool wait timeouts under heavy research load |
| **P2-5** | Hardcoded CORS Development Origins | Security | `backend/main.py` :: `origins` | Non-restricted CORS in production deployments |

---

### Priority P3 (Low Priority / Code Hygiene)

| Bug ID | Title | Component | File / Function | Risk |
|:---:|:---|:---|:---|:---|
| **P3-1** | Scratch files clutter in backend root directory | Repository | `backend/scratch_*.py` (18 files) | Code clutter |
| **P3-2** | Sequential vector loop in Spearman candidate scan | Performance | `backend/research/alpha/alpha_validator.py` | 6s minor delay in alpha discovery scan |

---

## Action Plan

> [!NOTE]
> **Status:** AUDIT COMPLETE. No code changes have been made.
> Awaiting user approval to proceed with P0 and P1 fixes.
