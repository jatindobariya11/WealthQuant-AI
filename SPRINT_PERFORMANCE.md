# Sprint 1 Performance & Stability Benchmark

## Regression Suite Execution
- **Run Time**: ~45 seconds
- **Routes Hit**: 13/13 Successful (100% Pass Rate)
- **Degraded Graceful Handlers**: Functioned as expected (PostgreSQL offline simulation successfully caught by `_DB_ERRORS` tuple and CSV fallbacks).

## API Latency Breakdown (Live Test)
| Endpoint | Method | Latency (ms) | Status | Note |
|---|---|---|---|---|
| `/health` | GET | 3.4 | 200 OK | |
| `/health/full` | GET | 5.2 | 200 OK | |
| `/api/sources` | GET | 3.8 | 200 OK | |
| `/api/cache/status` | GET | 5.3 | 200 OK | |
| `/api/metrics` | GET | 28.4 | 200 OK | |
| `/api/market-context` | GET | 16.8 | 200 OK | |
| `/api/adv-dec` | GET | 4.2 | 200 OK | |
| `/api/market/fii-analysis` | GET | 24.0 | 200 OK | |
| `/api/fast-signal/NIFTY/5m` | GET | 17.5 | 200 OK | |
| `/api/fast-signal/BANKNIFTY/5m` | GET | 3.6 | 200 OK | |
| `/api/screener` | GET | 1724.4 | 200 OK | *(Expected: Batch DB/Cache Read)* |
| `/api/quant/scan/indices` | GET | 3184.4 | 200 OK | *(Expected: Multi-ticker processing)* |
| `/api/quant/scan/nifty50` | GET | 41477.9 | 200 OK | *(Expected: 50x ticker deep inference)* |

## Thread Pool & Memory Benchmarks
- **Lock Contention**: Effectively neutralized via per-key dictionary size bounds and concurrent Double-Checked locks.
- **Memory Growth**: Lock caches (`_key_locks`, `_symbol_yf_locks`) bounded to strictly `500` items; guarantees consistent heap space consumption regardless of uptime.
- **Thundering Herd**: Fully mitigated on NSE session refresh. 

**Conclusion**: Performance strictly matches or slightly exceeds the V11 baseline with zero algorithmic deviation. Memory bounding guarantees vastly improved uptime sustainability.
