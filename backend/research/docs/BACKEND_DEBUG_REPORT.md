# WealthQuant V10.1 — Backend Architecture & Debug Audit

**Audit Date:** July 24, 2026  
**Target:** `backend/` Python codebase, modules, abstractions, imports, and pipeline consistency.

---

## 1. Architectural Overview & Module Separation

The backend is organized into core execution domains:
- **`main.py`**: Primary FastAPI application entrypoint and router mounting.
- **`pipeline/`**: Stage 1 to Stage 10 prediction pipeline engines.
- **`research/`**: Research Laboratory, Alpha Discovery, Incubation, and Replay engines.
- **`core/`**: Security, authentication, and core constants.
- **`data_fetcher.py` / `data_fetchers.py`**: Market data fetchers and exchange API integration.

---

## 2. Issues & Audit Findings

### Issue B-01 [Priority: P0] — PredictionStore In-Memory Lock Race Condition
- **File:** `backend/pipeline/prediction_store.py`
- **Function:** `PredictionStore.lock_prediction()` & `get_live()`
- **Problem:** Potential race condition when updating candle prediction locks across fast concurrent async requests without thread-level locking.
- **Root Cause:** In-memory `dict` mutation occurs without acquiring an explicit `asyncio.Lock()` or `threading.RLock()` across multi-threaded execution pools.
- **Evidence:** High frequency parallel calls to `/api/signals/fast` and `/api/dashboard/summary` can trigger concurrent read/write to `self._locks`.
- **Risk:** Prediction flickering if two requests compute slightly different microsecond signals before lock completion.
- **Suggested Fix:** Wrap lock creation and lookup inside an `asyncio.Lock()`.
- **Expected Improvement:** Guaranteed 100% atomic prediction locking per candle interval.

### Issue B-02 [Priority: P1] — Module Redundancy Between `data_fetcher.py` and `data_fetchers.py`
- **File:** `backend/data_fetcher.py` vs `backend/data_fetchers.py`
- **Function:** `fetch_fii_dii()` vs `get_fii_dii()`
- **Problem:** Duplicate data fetching logic for FII/DII, Global Markets, and Option chains across two separate files.
- **Root Cause:** Historical evolution of legacy endpoints alongside new pipeline fetchers.
- **Evidence:** `data_fetcher.py` (60KB) and `data_fetchers.py` (26KB) share overlapping HTTP requests to NSE cookie manager.
- **Risk:** Double HTTP requests to NSE server, increasing risk of cookie invalidation or rate-limiting.
- **Suggested Fix:** Refactor `data_fetchers.py` to act as a light alias wrapper calling `data_fetcher.py`.
- **Expected Improvement:** Reduces redundant external HTTP network calls by ~50%.

### Issue B-03 [Priority: P2] — Global Exception Handler Detail Leakage
- **File:** `backend/main.py`
- **Function:** `global_exception_handler()`
- **Problem:** Returns raw exception string `str(exc)` in 500 error response body.
- **Root Cause:** Exception handling formats stack trace details into `"detail": str(exc)`.
- **Evidence:** `main.py` lines 176-187.
- **Risk:** Internal database queries or file paths exposed to end-users during unhandled runtime exceptions.
- **Suggested Fix:** Sanitize exception response in production mode to return generic error message while logging raw stack trace internally.
- **Expected Improvement:** Hardened API security compliance.

### Issue B-04 [Priority: P2] — Scratch Files in Production Root
- **File:** `backend/scratch_*.py` (18 scratch files)
- **Problem:** Debug scripts (`scratch_api_test.py`, `scratch_pipeline_run.py`, etc.) clutter root backend folder.
- **Root Cause:** Temporary verification scripts saved in root directory during research iterations.
- **Evidence:** 18 files starting with `scratch_` in `backend/`.
- **Risk:** Code clutter and potential accidental import of scratch code.
- **Suggested Fix:** Move all scratch scripts into `backend/tests/scratch/`.
- **Expected Improvement:** Clean codebase structure.
