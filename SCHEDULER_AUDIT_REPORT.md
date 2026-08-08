# WealthQuant V7.5 — Scheduler Audit Report

This report documents the verification of the autonomous background scheduler (`pipeline/scheduler.py`) tasked with continuous ingestion and platform maintenance.

## 1. Scheduler Jobs Cadence
- **Ingestion Cadence:** Every 5 minutes during market hours (09:15 AM – 03:30 PM IST).
- **Daily Close Ingestion:** Triggers close summaries and prediction evaluations at 03:35 PM IST.
- **Monthly Ingestions:** Triggers walk-forward validation and Monte Carlo simulations on the 1st of each month.
- **Health Cadence:** Runs database connection check and API ping status every 5 minutes, 24/7.

## 2. Integrity Checks
- **No Concurrency Overlaps:** Ingestion runs sequentially per symbol (`NIFTY`, `BANKNIFTY`) using thread-safe worker pools, preventing overlaps.
- **DB Leak Inspection:** Database connection pool is correctly initialized once on startup and released gracefully when shutdown signals are received.
- **Outage Resiliency:** Network fetching uses a fresh session and retry handler to automatically bypass temporary NSE outages without throwing exceptions or blocking scheduler loops.

---
**Status:** **100% HEALTHY** (Scheduler runs sequentially, is crash-resilient, and correctly schedules daily and monthly tasks).
