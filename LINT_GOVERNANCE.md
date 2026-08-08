# Lint Governance Framework

## Overview
This document defines the strict governance policy for the static analysis and QA suite in the WealthQuant V12.0 architecture. 
It establishes the boundaries for what MUST be fixed and what MAY be suppressed to maintain high-velocity engineering without sacrificing reliability.

---

## Priority Classifications

### Priority 0 (P0) - Critical Architecture Integrity
**Status:** **MUST FIX IMMEDIATELY. NEVER SUPPRESS.**
- **Security Vectors**: SQL Injections (Bandit B608), Command Injections (B602, B603), Path Traversals.
- **Data Corruption**: Missing database transaction commits or rollbacks.
- **Race Conditions**: Shared mutable state without locks (Threading).
- **Memory Leaks**: Unbounded dictionary growth masquerading as caches.
- **Blind Exceptions**: Global `except Exception: pass` (BLE001) wrapping critical database or predictive logic.

### Priority 1 (P1) - Performance & Threading
**Status:** **MUST FIX. RARELY SUPPRESSED.**
- **Async Blocking**: Synchronous HTTP calls (`requests.get`) inside the main FastAPI Event Loop. Must be offloaded to ThreadPools.
- **Transaction Issues**: N+1 Query patterns (e.g., executing queries in a loop). Must be batched.
- **Cache Mutation**: Returning raw references to cached objects instead of deep copies.

### Priority 2 (P2) - Syntax Modernization & Types
**Status:** **SHOULD FIX. MAY BE SUPPRESSED FOR REFLECTION.**
- **Typing Integrity**: Adherence to PEP-585/PEP-604 (`list`, `X | None`).
- **MyPy Violations**: Missing argument typings.
- *Exceptions for Suppression*: Pydantic dynamic model fields, heavily decorated dependency injection wrappers.

### Priority 3 (P3) - Formatting & Styling
**Status:** **BEST EFFORT. EASILY SUPPRESSED.**
- **Ruff Format**: PEP-8 whitespace and spacing rules.
- **Import Ordering**: isort configurations.
- *Exceptions for Suppression*: Circular dependencies caused by strict alphabetical ordering (e.g. `yfinance/__init__.py`).

---

## General Suppression Policy
1. **No Global Ignores**: We do not use the `exclude` or `ignore` global arrays in `.toml` or `.yaml` configs to hide entire categories of rules.
2. **Explicit Line Exceptions**: Use `# noqa: [RULE]`, `# type: ignore`, or `# nosec [RULE]` directly on the offending line.
3. **Comment Justification**: Every `# noqa` or `# nosec` MUST be immediately preceded by a comment explaining the engineering justification for the bypass.
