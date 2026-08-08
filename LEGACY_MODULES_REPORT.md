# Legacy Modules Report

## Discovery
A full recursive file search was executed against the root `backend/` directory looking for disconnected module architectures, isolated sub-platforms, or abandoned test suites.

## Results
**25 legacy `scratch_*.py` files found.**

These modules were utilized for isolated component testing during earlier pipeline development phases, spanning:
- `scratch_debug_5m.py` (Local timeframe debugger)
- `scratch_gex_opt.py` (Isolated Gamma Exposure tester)
- `scratch_test_selenium.py` (Abandoned driver hook script)
- `scratch_pipeline_run.py` (Manual pipeline trigger script)

## Status
- **Unreachable**: None of these legacy scripts are imported, executed, or referenced by `main.py`, the ASGI Uvicorn app, the Locust testers, the `cache.py` threads, or the internal REST controllers.
- **Redundant**: Their functionality has been fully absorbed by the automated CI/CD load testers and the `certify_sprint2.py` suites.

## Recommendation
**DELETE**. They represent unused technical debt.
