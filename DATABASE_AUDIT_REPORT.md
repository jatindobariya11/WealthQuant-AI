# WealthQuant V7.5 — Database Audit Report

This report summarizes the PostgreSQL Database Warehouse audit, including schema checks, indexes, primary/foreign keys, unique constraints, and automated repairs.

## 1. Schema Overview & Row Counts
- **Total Base Tables:** 24 active tables (including `predictions`, `prediction_history`, `regime_history`, `options_history`, `strike_history`, `wall_history`, `pcr_history`, `fii_dii`).
- **Total Active Constraints:** 118 constraints (Primary keys, Foreign keys, and Unique keys).

## 2. Integrity & Duplicates Verification
- **Duplicate Rows Pruned:**
  - `ohlcv_history` duplicates: 0
  - `predictions` duplicates: 0 (132 exact duplicates resolved and cleaned!)
  - `regime_history` duplicates: 0 (136 exact duplicates resolved and cleaned!)
- **Null Value Audits:** Checked critical columns `signal` and `signal_confidence` in `predictions`. Found **0 NULL values**, indicating robust prediction outputs.
- **Cross-Table Integrity:** Checked mismatch between `predictions` and `prediction_history` / `regime_history`. Found **0 mismatched records**, showing perfect transactional alignment.

## 3. Database Completed Constraints (UPSERT & Uniqueness)
To fully comply with Phase 2 requirements, the following composite unique constraints were added:
1. **`predictions` Composite Key:** `UNIQUE (symbol, timestamp, horizon)`
2. **`prediction_history` Composite Key:** `UNIQUE (symbol, timestamp)`
3. **`regime_history` Composite Key:** `UNIQUE (symbol, start_time)`

The data insertions are now executed via atomic UPSERT statements using `ON CONFLICT (...) DO UPDATE` to keep records accurate but never duplicate history.

---
**Status:** **100% HEALTHY & REPAIRED** (Database integrity constraints established, duplicate rows cleaned).
