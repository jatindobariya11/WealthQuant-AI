# Tool Configuration Guide

## Philosophy
WealthQuant enforces an aggressively secure, yet dynamically tolerant static analysis configuration. We recognize that AI quantitative modeling requires runtime reflection, JIT model loading, and heavy dependency injection that out-of-the-box linters struggle to trace.

## 1. Ruff (Linter & Formatter)
- **Engine Role**: Replaces Flake8, Isort, Black, PyUpgrade.
- **Mandatory Rules**: `E` (Error), `F` (Pyflakes), `UP` (PyUpgrade), `I` (Isort), `B` (Bugbear), `BLE` (Blind Exceptions).
- **Ignored Globally**: `None`.
- **Per-File Allowed Ignores**: 
  - `# ruff: noqa: F401` -> Permitted for optional plugin library `try/except` loads.
  - `# ruff: noqa: I001` -> Permitted strictly for `__init__.py` files where alphabetizing breaks runtime module loads.
- **Review Schedule**: Continuous / PR Level.

## 2. Vulture (Dead Code Detection)
- **Engine Role**: Ensures the codebase remains pruned of abandoned modules.
- **Mandatory Configuration**: Must run with `--min-confidence 60`.
- **Whitelist File (`vulture_whitelist.py`)**:
  - All FastAPI routers (`@router.get`, `@app.on_event`).
  - All Pydantic model payload variables.
  - Locust HTTP test suite structures (`WealthQuantLoadUser`).
- **Review Schedule**: Sprintly (Pre-Release Phase).

## 3. Bandit (Security Scanning)
- **Engine Role**: SAST for detecting severe Python security vulnerabilities (Injection, Exec, Subprocess).
- **Mandatory Configuration**: Fails pipeline on `HIGH` and `MEDIUM` severity issues.
- **Ignored Globally**: `None`.
- **Per-File Allowed Ignores**:
  - `# nosec B108` -> Allow `/tmp/` usage explicitly for NVMe-backed fast Replay Engine RAM storage.
  - `# nosec B301` -> Allow `pickle.loads()` exclusively in the Bayesian isolated worker layer when deserializing trusted local caching states. Never on user input.
- **Review Schedule**: Continuous / PR Level.

## 4. MyPy (Type Checking)
- **Engine Role**: Strictly types the internal quantitative interfaces.
- **Configuration Philosophy**: `ignore_missing_imports = True` for heavy ML libraries (`tensorflow`, `hmmlearn`, `xgboost`) since they lack proper stub files, but strictly typed internal business logic.
- **Per-File Allowed Ignores**: `# type: ignore` is permitted when crossing boundaries between Pydantic validation and SQLAlchemy ORM bindings.
- **Review Schedule**: Continuous / PR Level.
