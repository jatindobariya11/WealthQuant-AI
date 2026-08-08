# PERFORMANCE PROFILE
## py-spy and tracemalloc results
- Hotspots: JSON serialization in Dashboard route.
- Memory Allocation: Peak memory 400MB during heavy prediction generation.
- Bottlenecks: Network IO during NSE fetches (mitigated by async).

Generated: 2026-07-31T23:10:41.866777