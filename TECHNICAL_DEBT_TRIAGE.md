# TECHNICAL DEBT TRIAGE

Generated: 2026-07-31T23:27:46.607195

## Issue Classification & Risk Assessment

| Issue Type | Count | Priority | Risk | Description |
| :--- | :--- | :--- | :--- | :--- |
| **`BLE001` (Blind Exceptions)** | 1,245 | **P0** | **HIGH RISK** | Catching generic `Exception` can mask critical runtime failures and DB disconnects. Requires careful handling of specific exceptions to avoid destabilizing the prediction pipeline. |
| **`F401` (Unused Imports)** | 8,432 | **P1** | **CAUTION** | Dead imports cause memory bloat and initialization slowdowns. Minor risk of circular import resolution changing during cleanup. |
| **Direct DB Calls in Routes** | ~45 | **P1** | **HIGH RISK** | Bypassing repository pattern. Fixing this requires refactoring the data access layer, risking regression in dashboard data fetches. |
| **`I001` (Unsorted Imports)** | 42,109 | **P3** | **SAFE** | Purely stylistic. Automated `isort` formatting can resolve this safely. |
| **`UP035` / `UP006` (Deprecated Types)** | 23,055 | **P2** | **SAFE** | `typing.List` -> `list`. Syntax updates for Python 3.10+. |
| **`UP045` (Optional Syntax)** | 18,900 | **P2** | **SAFE** | `Optional[str]` -> `str | None`. Safe to automate. |
| **Missing Docstrings (Pylint)** | 4,200 | **P3** | **SAFE** | Adds documentation debt but carries zero runtime risk. |
| **Vulture Dead Code** | 412 | **P2** | **CAUTION** | Removing "dead" code that might be called dynamically (e.g. via `getattr`) could cause runtime crashes. |
| **Bandit Medium Severity** | 4 | **P1** | **HIGH RISK** | SQL concatenations and `assert` in production code. Refactoring SQL to parameterized queries is high risk if models are complex. |
