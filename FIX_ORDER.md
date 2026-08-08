# FIX ORDER & STRATEGY

Generated: 2026-07-31T23:27:46.607195

## Suggested Fix Execution Order

To minimize merge conflicts and pipeline regression, technical debt must be resolved in this exact sequence:

1. **[P3] [SAFE] Syntax & Imports (Ruff Auto-Fixes)**
   - Resolves `I001`, `UP006`, `UP035`, `UP045`, `F401`
   - **Why first?** Clears 90% of the noise (approx 90,000 issues) safely, making subsequent reviews much easier.

2. **[P2] [CAUTION] Dead Code Removal (Vulture)**
   - Manually verify the 412 orphaned functions/variables.
   - **Why second?** Reduces the surface area for the complex refactors. No need to fix `BLE001` in code that's going to be deleted.

3. **[P1] [HIGH RISK] Security & DB Refactoring**
   - Address the 4 Bandit SQL vulnerabilities.
   - Refactor direct route DB queries into the Repository pattern.
   - **Why third?** Core architectural fixes that require rigorous unit testing after implementation.

4. **[P0] [HIGH RISK] Blind Exception Remediation (`BLE001`)**
   - Replace `except Exception:` with specific `except (KeyError, ValueError, asyncpg.PostgresError):` where applicable.
   - **Why last?** Changing error handling logic is the most likely source of systemic regression. Must be done only when the rest of the codebase is clean and predictable.
