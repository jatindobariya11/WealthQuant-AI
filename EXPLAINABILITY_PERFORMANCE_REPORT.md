# Explainability Performance Report

## Problem Statement
The Explainability Engine (`update_and_analyze` method) was performing synchronous File I/O operations (reading and writing large CSV fallback files) every time a prediction was evaluated. Furthermore, the downstream `_run_analysis_pipeline` (Phases 2-6 evaluation algorithms) was also being awaited synchronously on the main thread. This caused severe Event Loop blocking, leading to 10+ second timeouts on API requests like `/api/pipeline/NIFTY?interval=15m`.

## Optimizations Implemented

1. **Bypass CSV on DB Success**
   The CSV update logic was modified to only execute if the primary PostgreSQL database update fails, OR if the environment variable `WEALTHQUANT_DEBUG_CSV=1` is explicitly set. This skips the expensive `pd.read_csv` and `pd.DataFrame.to_csv` calls entirely in normal production mode.

2. **Asynchronous Historical Recomputation**
   The heavy bulk explainability recomputation (`self._run_analysis_pipeline(symbol)`) was decoupled from the main request flow.
   - **Before:** `await self._run_analysis_pipeline(symbol)` (Synchronous block)
   - **After:** `asyncio.create_task(self._run_analysis_pipeline(symbol))` (Fire-and-forget background task)

## Verification
- Dashboard API requests now return immediately, without waiting for the background analysis pipeline to complete.
- Timeouts on `/api/pipeline/NIFTY?interval=15m` have been completely eliminated.
