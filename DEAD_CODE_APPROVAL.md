# Dead Code Approval Form

## Overview
This document contains the final proposed candidates for deletion during Sprint 4. 
**No code has been deleted.** Please review this list and reply with your approval (or modified instructions) for each section before execution.

---

### Candidate Group 1: Legacy Scratch Scripts
**Description**: Temporary debug files prefixed with `scratch_` located in the root of `backend/`. These are out-of-date and bloat the repository.

- `backend/scratch_api_test.py`
- `backend/scratch_calibration_test.py`
- `backend/scratch_check_nan.py`
- `backend/scratch_debug_5m.py`
- `backend/scratch_explainability_test.py`
- `backend/scratch_explainability_test_v6.py`
- `backend/scratch_get_all.py`
- `backend/scratch_get_predictions.py`
- `backend/scratch_get_ram.py`
- `backend/scratch_get_scheduler.py`
- `backend/scratch_gex_opt.py`
- `backend/scratch_global.py`
- `backend/scratch_inst_test.py`
- `backend/scratch_kill_port.py`
- `backend/scratch_monitor_test.py`
- `backend/scratch_pain_opt.py`
- `backend/scratch_pg_check.py`
- `backend/scratch_pipeline_run.py`
- `backend/scratch_query_fast.py`
- `backend/scratch_router_test.py`
- `backend/scratch_test.py`
- `backend/scratch_test_nse.py`
- `backend/scratch_test_selenium.py`
- `backend/scratch_v8_verify.py`
- `backend/scratch_warehouse_run.py`

**Recommendation**: **DELETE ALL**
**Risk Level**: **NONE** (Never imported by production code)

---

### Candidate Group 2: Unused Standard Imports (F401)
**Description**: 446 unused imports detected by Ruff (mostly `typing.List`, `typing.Dict`, `typing.Union`, `typing.Optional`) across the codebase after Sprint 3's PyUpgrade modernization.

**Recommendation**: **DELETE/CLEANUP**
**Risk Level**: **NONE** (Cleaning up imports does not affect runtime logic)

---

### Candidate Group 3: Vulture False Positives (DO NOT DELETE)
**Description**: Vulture identified several FastAPI routes (`startup_event`, `get_experiments`, etc. in `research_dashboard.py` and `replay_routes.py`) and Locust load test classes (`WealthQuantLoadUser`) as unused because they are triggered by frameworks/reflection rather than direct Python imports.

**Recommendation**: **KEEP**
**Risk Level if Deleted**: **HIGH** (Would break API routes and test suites)

---

**Awaiting Your Approval:** Please explicitly approve the deletion of Candidate Group 1 and 2, while retaining Group 3.
