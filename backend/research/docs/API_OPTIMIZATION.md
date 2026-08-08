# WealthQuant API Layer Optimization Plan

**Audit Date:** July 24, 2026  
**Target:** FastAPI Routes, Request Payload Size, JSON Serialization, Aggregated Endpoints.

---

## 1. Identified API Bottlenecks & Optimization Items

### Item API-OPT-01: Single Aggregated Dashboard Endpoint (`/api/dashboard/{symbol}`)
- **Status:** Integrated in V8.6/V10.1.
- **Impact:** Replaced 6 individual HTTP calls (`/api/prediction`, `/api/options`, `/api/regime`, `/api/health`, `/api/scheduler`, `/api/explainability`) with 1 unified payload.
- **Result:** Reduced client network roundtrips from 6 to 1 (**83% reduction in HTTP overhead**).

### Item API-OPT-02: Compact JSON Response Payload Trimming
- **Target Endpoints:** `/api/dashboard/{symbol}`, `/api/signals/fast`
- **Current Behavior:** Returns null fields and redundant verbose metadata keys in default response dicts.
- **Proposed Optimization:** Enable `response_model_exclude_unset=True` or strip empty null structures on production endpoints.
- **Estimated Improvement:** Reduces response payload byte size by **~35%** (from 48KB to 31KB).

### Item API-OPT-03: HTTP GZip Response Compression Middleware
- **Component:** `backend/main.py`
- **Proposed Optimization:** Add `GZipMiddleware(minimum_size=1000)` for JSON responses > 1KB.
- **Estimated Improvement:** **+75% Bandwidth Savings** on option chain payloads (48KB compressed to ~9KB over network).
