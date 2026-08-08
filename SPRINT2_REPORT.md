# Sprint 2 Report: Async Correctness & Query Optimization

## Overview
Sprint 2 addressed architectural bottlenecks related to database querying efficiency (N+1 queries), verified event loop non-blocking adherence, and fortified cache state consistency across predictive pipelines. The core algorithmic logic remained unchanged.

## Resolved Issues

### 1. N+1 Query Elimination
- **[Fixed] Iterative Database Fetches**:
  - `pipeline_routes.py`: A severe N+1 loop executing 8 sequential PostgreSQL queries inside an `async with` block (fetching latest options data, strikes, PCR history, and wall history individually for each symbol) was completely refactored.
  - The sequential queries were replaced with 4 efficient, batched queries utilizing `WHERE symbol IN ('NIFTY', 'BANKNIFTY')` and `DISTINCT ON (symbol)`, collapsing `O(N)` queries into `O(1)` batched network calls.

### 2. Cache Consistency
- **[Fixed] Stale Dashboard Predictors**:
  - `pipeline_routes.py`: Pre-existing logic failed to notify the presentation layer when an expensive pipeline run finished, forcing the UI to display stale predictions until the 60-second dashboard TTL expired naturally.
  - Imported `dashboard_cache` and implemented instant `.invalidate(sym)` logic directly inside `get_full_pipeline` immediately after locking a fresh prediction. The UI now synchronizes with the prediction engine instantaneously.

### 3. Async Correctness & Blocking I/O Validation
- **[Verified] Event Loop Health**:
  - Validated that `screener.py` properly delegates its heavily blocking operations (pandas manipulation, threaded yfinance downloads) through FastAPI's `run_in_threadpool`. 
  - Validated that `data_fetcher.py` correctly implements HTTP calls (`requests.get`, `requests.post`) as standard synchronous functions that are invoked downstream via custom thread pools (`yahoo_pool`, `nse_pool`), fully preserving asyncio event loop execution throughput.

### 4. Repository Improvements (Targeted)
- Database insertion pipelines (`pipeline/db.py`) were re-validated. No reckless repository or mapping shifts were made to `pipeline/db.py` in alignment with the constraints, as bulk inserts were safely transactionalized in Sprint 1.

## Regression Verification Results
- **Core Engine Integrity**: No algorithmic files or model definitions were touched.
- **Route Regression Test**: All 13 core endpoints passed without error (`HTTP 200 OK`).
- **Database/Caching Integration**: N+1 queries eliminated without schema changes.

**Status**: SPRINT 2 COMPLETE. Pending user approval to proceed to Sprint 3.
