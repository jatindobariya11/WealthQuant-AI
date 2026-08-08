# CLEANUP ROADMAP

Generated: 2026-07-31T23:27:46.610204

## Cleanup Roadmap

### Phase 1: Automated Formatting (Safe)
- Run `ruff check . --fix`
- **Expected Outcome:** 90,000+ stylistic and import issues resolved instantly.

### Phase 2: Dead Code Pruning (Caution)
- Audit Vulture output line-by-line.
- Remove confirmed dead endpoints and unused quantitative utility functions.
- **Expected Outcome:** ~2,000 LOC removed.

### Phase 3: Structural Refactoring (High Risk)
- Move DB access from `server.py` to `db.py` repository methods.
- Sanitize SQL queries identified by Bandit.
- **Expected Outcome:** Clean separation of concerns.

### Phase 4: Exception Hardening (High Risk)
- Target all 1,245 `BLE001` violations.
- Inject specific Exception types (`httpx.TimeoutException`, `KeyError`, etc).
- **Expected Outcome:** Improved fault isolation; failures are explicitly tracked in `SYSTEM_HEALTH`.

---
**Status: TRIAGE COMPLETE.**
**Ready for Cleanup Phase upon user approval.**
