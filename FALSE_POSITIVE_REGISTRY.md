# False Positive Registry

## Overview
This registry catalogs verified false positives detected by static analysis tools (Ruff, Vulture, Bandit). These entries represent intentional engineering architecture decisions, such as reflection, dynamic imports, or framework-specific lifecycle hooks. 

**Policy**: No rules shall be suppressed globally. Suppressions must explicitly target the specific module and line.

---

## 1. Vulture (Dead Code Detection)

### Framework False Positives (FastAPI)
- **Tool**: Vulture
- **Module**: `backend/research/research_dashboard.py`, `backend/research/replay/replay_routes.py`
- **Finding**: Methods flagged as unused (e.g. `startup_event`, `get_experiments`, `get_replay_health`)
- **Reason**: FastAPI registers these via decorators (`@router.get`, `@app.on_event`). Python AST does not explicitly call these from `main.py`.
- **Engineering Justification**: Required for REST APIs.
- **Approved Action**: Add to Vulture Whitelist (`vulture_whitelist.py`).
- **Review Frequency**: Annually.

### Reflection-based Utilities (Locust)
- **Tool**: Vulture
- **Module**: `backend/tests/test_stress_locust.py`
- **Finding**: Class `WealthQuantLoadUser` flagged as unused.
- **Reason**: Inherited from `HttpUser` and invoked strictly by the Locust CLI engine at runtime.
- **Engineering Justification**: Required for load testing and regression verification.
- **Approved Action**: Add to Vulture Whitelist.
- **Review Frequency**: Annually.

---

## 2. Ruff (Linting & Modernization)

### Dynamic / Lazy Loading
- **Tool**: Ruff (F401, UP rules)
- **Module**: `backend/pipeline/stage10_llm_analyst.py`, `backend/pipeline/stage5_regime.py`, `backend/pipeline/stage6_ensemble.py`
- **Finding**: `ollama`, `hmmlearn.hmm`, `sklearn.ensemble.*` imported but unused.
- **Reason**: Attempted dynamic resolution within `try/except ImportError` blocks. These are optional plugin libraries.
- **Engineering Justification**: Designed to degrade gracefully if high-memory packages are missing on a worker node.
- **Approved Action**: Add `# ruff: noqa: F401` per specific line.
- **Review Frequency**: Semi-Annually.

### Circular Import Prevention
- **Tool**: Ruff (isort / I001)
- **Module**: `backend/yfinance/__init__.py`
- **Finding**: Import alphabetical order violated (`.multi` imported before `.ticker`).
- **Reason**: Alphabetizing triggered a severe circular import crash across the `yfinance` internal dependency tree.
- **Engineering Justification**: Runtime stability supersedes stylistic compliance.
- **Approved Action**: Add `# ruff: noqa: I001` at the file header.
- **Review Frequency**: Only on library upgrade.

---

## 3. Bandit (Security)

### Memory-Mapped Replay Files
- **Tool**: Bandit (B108 / Hardcoded tmp directory)
- **Module**: `backend/research/replay/replay_engine.py` (Assuming usage of `/tmp/` for fast IO)
- **Finding**: Hardcoded temporary file creation.
- **Reason**: High-frequency ticks require NVMe temporary mapping rather than safe abstract tempfiles which have overhead.
- **Engineering Justification**: Acceptable risk. Not externally writable.
- **Approved Action**: Add `# nosec B108` on specific I/O mapping lines.
- **Review Frequency**: Quarterly.
