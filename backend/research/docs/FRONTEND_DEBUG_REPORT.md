# WealthQuant V10.1 — Frontend Architecture & Debug Audit

**Audit Date:** July 24, 2026  
**Target:** `frontend/` React Application, Components, Hooks, Data Polling, and UI Rendering.

---

## 1. Overview

The frontend is a React SPA rendering real-time market signals, institutional metrics, options chains, and research analytics.

---

## 2. Audit Findings

### Issue F-01 [Priority: P1] — Missing `AbortController` in Polling Effects
- **File:** `frontend/src/pages/Dashboard.js`
- **Function:** `useEffect()` data fetching hook
- **Problem:** API calls issued during 5-second interval polling do not cancel when navigating between tabs.
- **Root Cause:** Standard `fetch()` calls lack an `AbortSignal`.
- **Evidence:** Rapid navigation between Dashboard, Options, and Research pages leaves pending HTTP calls executing in background.
- **Risk:** Unneeded network traffic and React "state update on unmounted component" warnings.
- **Suggested Fix:** Instantiate `const controller = new AbortController()` inside `useEffect` and return `() => controller.abort()` in cleanup.
- **Expected Improvement:** 0 unmounted state memory leaks and reduced network overhead.

### Issue F-02 [Priority: P2] — Sub-optimal Component Re-rendering in Option Chain Table
- **File:** `frontend/src/components/OptionsChainTable.js`
- **Problem:** Entire strike table re-renders on minor sub-second spot price ticks.
- **Root Cause:** Large strike array is passed as an un-memoized prop without `React.memo` or `useMemo`.
- **Evidence:** High DOM node update frequency in Chrome React DevTools Profiler during fast market feeds.
- **Risk:** Slight UI frame drops on lower-spec client hardware.
- **Suggested Fix:** Wrap row components in `React.memo` and memoize strike transformation with `useMemo`.
- **Expected Improvement:** 60 FPS smooth rendering during volatile market sessions.

### Issue F-03 [Priority: P2] — Hardcoded Localhost API Fallbacks
- **File:** `frontend/src/api/config.js`
- **Problem:** API base URL defaults to `http://localhost:8000` without fallback to relative paths in production environments.
- **Root Cause:** Environment variable `REACT_APP_API_URL` missing default relative fallback `/api`.
- **Risk:** Requires manual build config change when deploying to non-localhost staging environments.
- **Suggested Fix:** Default `API_BASE_URL` to `process.env.REACT_APP_API_URL || '/api'`.
- **Expected Improvement:** Environment-agnostic build deployment.
