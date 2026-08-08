# WealthQuant V10.1 — Scheduler & Background Task Audit

**Audit Date:** July 24, 2026  
**Target:** `pipeline/scheduler.py`, Task Overlap Guards, Memory Leaks, Retry Logic, and Background Jobs.

---

## 1. Overview

The background scheduler `wq_scheduler` operates 24/7 data collection and signal computation loops.

---

## 2. Audit Findings

### Issue SCHED-01 [Priority: P1] — Job Overlap Prevention Guard
- **File:** `backend/pipeline/scheduler.py`
- **Function:** `_collect_options_job()`
- **Problem:** If network latency slows down NSE cookie fetch, a 1-minute scheduled job could potentially spawn a concurrent second invocation before the first finishes.
- **Root Cause:** Absence of an `is_running` flag or `asyncio.Lock()` per job function.
- **Evidence:** Network delay spikes up to 45 seconds during NSE server throttling.
- **Risk:** Duplicate jobs competing for exchange cookies and CPU time.
- **Suggested Fix:** Wrap job execution body in `async with self._job_locks[job_name]:` or skip if `self._running_jobs[job_name]` is True.
- **Expected Improvement:** 100% prevention of job execution overlap.

### Issue SCHED-02 [Priority: P2] — Exception Recovery & Exponential Backoff
- **File:** `backend/pipeline/scheduler.py`
- **Problem:** Fixed 5-second sleep on network errors during cookie refresh.
- **Root Cause:** Constant retry interval.
- **Suggested Fix:** Implement exponential backoff (e.g. 2s, 4s, 8s, 16s, max 60s) with jitter.
- **Expected Improvement:** Prevents hammering external endpoints during temporary exchange outages.
