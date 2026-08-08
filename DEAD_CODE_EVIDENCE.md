# Dead Code Evidence Log

## Vulture Static Analysis Hits

Vulture analyzed the AST of all `.py` files inside the `backend/` directory (excluding `yfinance` dependencies).

### 1. FastAPI Framework False Positives (KEEP)
Vulture relies on direct Python imports and calls to build its AST dependency tree. It flags FastAPI endpoint methods as unused because they are invoked dynamically through HTTP routes.
*Evidence:*
- `research_dashboard.py:47`: `startup_event` (60% confidence) -> `app.on_event("startup")`
- `research_dashboard.py:58`: `get_experiments` -> `@router.get("/experiments")`
- `replay_routes.py:36`: `get_replay_health` -> `@router.get("/health")`

### 2. Locust Reflection False Positives (KEEP)
*Evidence:*
- `test_stress_locust.py:6`: `WealthQuantLoadUser` -> Inherits from `HttpUser`, invoked by Locust CLI engine, not imported directly.

### 3. Temporary Variables (KEEP)
*Evidence:*
- `performance_analyzer.py:19-58`: Assorted performance baseline attributes (`baseline_sortino`, `enhanced_calmar`). Kept for algorithmic expandability.

### 4. Scratch Files (DELETE)
*Evidence:*
- 25 files matching `scratch_*.py` located in root. These contain test data, manual HTTP queries, and abandoned debugging hooks. None are referenced anywhere in `main.py` or the application routers.
