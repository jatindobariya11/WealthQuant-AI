# Final False Positive Report

## Suppressed Intentional Engineering Patterns

| Type | Module | Reason | Action Taken |
| :--- | :--- | :--- | :--- |
| **Dead Code Detection** | `research_dashboard.py`, `replay_routes.py` | FastAPI dynamic route registration decorators. | `vulture_whitelist.py` populated with all REST path hooks. |
| **Dead Code Detection** | `test_stress_locust.py` | Framework-specific load testing class invoked dynamically by Locust CLI. | Whitelisted `WealthQuantLoadUser`. |
| **Unused Imports (F401)** | `stage5_regime.py`, `stage6_ensemble.py` | `try/except ImportError` blocks designed to isolate optional ML plugins without crashing the core app. | ` # ruff: noqa: F401` inserted on specific import lines. |
| **Import Ordering (I001)** | `yfinance/__init__.py` | Alphabetical `isort` caused fatal circular dependency within module. | `# ruff: noqa: I001` inserted at file head. |

All suppressions have been carefully reviewed against the `LINT_GOVERNANCE.md` strict protocols and isolated directly to their offending line or explicit whitelist array. No global suppression logic was permitted.
