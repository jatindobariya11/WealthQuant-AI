# WealthQuant V7.5 — Project Structure Audit Report

This report documents the structural integrity of the WealthQuant platform codebase, including scanned files, dead code detections, dependency patterns, and unused scratch scripts.

## 1. Directory Walk & Scanned Files
- **Total Python Modules Scanned:** 5,049
- **Unused/Scratch Scripts Detected:** 13 files in the backend root directory (e.g. `scratch_api_test.py`, `scratch_calibration_test.py`, `scratch_explainability_test.py`, `scratch_gex_opt.py`, `scratch_pain_opt.py`, `scratch_router_test.py`, `scratch_test.py`).
- **Recommendation:** Prune these temporary scratch files or move them into a `scratch/` subdirectory to maintain backend directory cleanliness.

## 2. Dead Code & Redundant Modules
- **Dual Data Fetcher Dependency:** The files `data_fetcher.py` and `data_fetchers.py` exist concurrently. Multiple active python scripts (`main.py`, `options_analyzer.py`, `signaldesk_engine.py`, `options_collector.py`, `stage1_market_adapter.py`) import/reference symbols from both.
- **Divergence:** `data_fetcher.py` is the primary statistical ingestion engine, whereas `data_fetchers.py` contains utility methods for live options chain downloading and session retries.
- **Recommendation:** Consolidate these into a single module named `data_fetcher.py` in a future release to avoid import confusion and naming conflicts.

## 3. Deprecated Modules & Library Usage
- **Distutils Warnings:** 139 locations were scanned referencing the deprecated `distutils` package (mostly within local environment scripts and build configurations under `.venv\`). This does not affect runtime backend operations, but dependencies should be updated to use modern alternatives (e.g. `sysconfig`, `setuptools`).

---
**Status:** **PASSED WITH WARNINGS** (Ready for continuous execution, consolidation of fetcher modules recommended).
