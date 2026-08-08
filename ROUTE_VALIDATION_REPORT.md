# ROUTE VALIDATION REPORT

Generated: 2026-08-01T13:22:01
Backend: http://127.0.0.1:8000

**Summary:** 13 passed / 0 failed

| Status | Route | Endpoint | HTTP | Latency |
|--------|-------|----------|------|---------|
| [OK] | Health Check | `/health` | 200 | 24.8ms |
| [OK] | Full Health Check | `/health/full` | 200 | 17.2ms |
| [OK] | Data Sources | `/api/sources` | 200 | 16.1ms |
| [OK] | Cache Status | `/api/cache/status` | 200 | 4.4ms |
| [OK] | Platform Metrics | `/api/metrics` | 200 | 25.3ms |
| [OK] | Market Context | `/api/market-context` | 200 | 8338.8ms |
| [OK] | Advance/Decline | `/api/adv-dec` | 200 | 17.5ms |
| [OK] | FII Analysis | `/api/market/fii-analysis` | 200 | 36.8ms |
| [OK] | Screener | `/api/screener` | 200 | 2297.4ms |
| [OK] | Fast Signal (NIFTY 5m) | `/api/fast-signal/NIFTY/5m` | 200 | 22.6ms |
| [OK] | Fast Signal (BANKNIFTY 5m) | `/api/fast-signal/BANKNIFTY/5m` | 200 | 15.6ms |
| [OK] | Quant MTF Scan (Nifty50) | `/api/quant/scan/nifty50` | 200 | 51281.4ms |
| [OK] | Quant MTF Scan (Indices) | `/api/quant/scan/indices` | 200 | 3517.9ms |

---
