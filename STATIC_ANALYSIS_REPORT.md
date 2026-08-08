# STATIC ANALYSIS REPORT

Generated: 2026-07-31T23:17:40.007905

## Static Analysis Summary
The raw static analysis outputs were too large to embed fully (>100,000 lines for Ruff).

### Ruff
- **Warnings/Errors:** 100,273+ issues detected.
- **Top Issues:** `I001` (Unsorted imports), `F401` (Unused imports), `BLE001` (Blind exceptions), `UP006` (Deprecated type hints like `typing.List`).

### Pylint
- Codebase requires extensive refactoring for missing docstrings, variable naming conventions, and too-many-locals.

### MyPy (Type Safety)
- Type safety is compromised in many modules due to implicit `Optional` and `Any` types, especially in pandas/numpy interactions.

*(Detailed logs have been dumped to `ruff_out.txt` and `mypy_out.txt`)*
