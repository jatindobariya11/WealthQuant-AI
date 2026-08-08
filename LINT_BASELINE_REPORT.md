# Lint Baseline Report

## Tool Audits

### 1. Vulture (Dead Code)
- **Whitelist Applied:** `vulture_whitelist.py` (FastAPI lifecycle hooks, Pydantic data schemas, Locust reflection wrappers).
- **Current Status:** 100% of false-positive core backend framework warnings have been cleanly suppressed. The only remaining alerts belong to optional experimental components (e.g. `statistical_validation.py`) and third-party libraries (e.g. `yfinance`).

### 2. Ruff (Syntax, Imports, Linting)
- **Rules Fixed in Sprint 3/5:** `F401`, `UP`, `I`, `BLE001`.
- **Suppressions Applied:** 
  - `yfinance/__init__.py`: `# ruff: noqa: I001` to prevent circular imports caused by alphabetizing.
  - `pipeline/stage5`, `stage6`, `stage10`: `# ruff: noqa: F401` to allow runtime JIT import isolation for heavy ML packages.
- **Current Status:** 0 actionable issues remaining in backend core logic.

### 3. Bandit (Security)
- **Actionable Findings Fixed (Sprint 1):** SQL Injections (B608) patched.
- **Suppressions Audited:** 
  - Isolated `/tmp/` usage explicitly justified for NVMe Replay Storage.
  - Safe `pickle.loads` isolated in local state synchronization.
- **Current Status:** 0 actionable security warnings in backend execution.

### 4. MyPy (Typing)
- **Status:** Typed strictly for business logic, permitting `Any` for third-party DataFrames to prevent arbitrary structural blocking.

**Result:** The linting pipeline produces clean, actionable reports free of framework-specific noise.
