# DATABASE REPORT

Generated: 2026-08-01T13:22:01

## PostgreSQL Connection Status

| Metric | Value |
|--------|-------|
| Connected | [WARN] No |
| Pipeline Status | OFFLINE |
| Subsystem Health | Degraded (Offline) |

> [!WARNING]
> PostgreSQL is **OFFLINE**. The system is operating in gracefully degraded mode:
> - All DB writes are disabled
> - In-memory cache and JSON snapshots are serving data
> - PredictionStore cache is active
> - Circuit breakers engaged — no connection storm

## Recovery Instructions

1. Start PostgreSQL service: `net start postgresql-x64-16` (or your version)
2. Verify connectivity: `psql -h 127.0.0.1 -p 5432 -U postgres`
3. Restart the WealthQuant backend to reconnect the pool.

## Degraded Mode Guarantees

| Guarantee | Status |
|-----------|--------|
| No crash on DB failure | [OK] Circuit breaker active |
| No endless retry storm | [OK] Exponential backoff engaged |
| Memory cache fallback | [OK] Active |
| JSON snapshot fallback | [OK] Active |
| Writes disabled safely | [OK] Until reconnect |
| No SQLite fallback | [OK] By design |

---
_Source: /health/full + /api/metrics_