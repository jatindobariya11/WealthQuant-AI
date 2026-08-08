# FALSE POSITIVE REPORT

Generated: 2026-07-31T23:27:46.609205

## False Positives & Exclusions

The following issues were flagged by static analysis but are **intentionally ignored** due to framework requirements or quantitative logic constraints:

1. **Lazy Imports inside Functions (`F401` / `E402`)**
   - **Flagged as:** Unused or improperly placed import.
   - **Reality:** We intentionally import `yfinance` and `pandas` inside specific data-fetching functions to prevent circular dependencies and speed up Uvicorn startup.
   - **Action:** Add `# noqa: F401` or configure Ruff to ignore.

2. **Vulture "Dead Code" in Models**
   - **Flagged as:** Unused Pydantic fields or DB model columns.
   - **Reality:** Fields mapped directly to JSON payloads from NSE API that are implicitly accessed via `**kwargs` or `.dict()`.
   - **Action:** Whitelist these data classes.

3. **Bandit Low Severity (Hardcoded /tmp paths)**
   - **Flagged as:** Insecure temporary file creation.
   - **Reality:** Replay engine strictly requires memory-mapped `/tmp` files for high-frequency tick data.
   - **Action:** Acknowledge and suppress.
