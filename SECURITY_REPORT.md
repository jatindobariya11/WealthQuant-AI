# SECURITY REPORT

Generated: 2026-07-31T23:17:40.011928

## Bandit Security Scan Summary
- **Severity High:** 0
- **Severity Medium:** 4 (Mostly `assert` statements used in production code and some raw SQL concatenations).
- **Severity Low:** 12 (Hardcoded temporary directories and `try/except Exception: pass` blocks).

*(A full sanitization pass is required during the cleanup phase).*
