# WealthQuant V8.3 — Model & API Regression Test Plan

**Purpose:** Ensure zero numerical drift in quantitative models and zero breaking changes in REST API response schemas across code updates.  

---

## 1. REGRESSION TESTING STRATEGY

```
   ┌───────────────────────┐       ┌───────────────────────┐
   │  Current Pipeline     │       │  Golden Baseline      │
   │  Execution Output     │       │  Reference JSON       │
   └───────────┬───────────┘       └───────────┬───────────┘
               │                               │
               └───────────────┬───────────────┘
                               │
                       ┌───────▼───────┐
                       │ Numerical &   │
                       │ Schema Diff   │
                       └───────┬───────┘
                               │
                       ┌───────▼───────┐
                       │ Tolerance     │
                       │ Check (10⁻⁴)  │
                       └───────────────┘
```

The regression suite compares live output against immutable **Golden Reference Baselines** generated for standard market inputs (NIFTY and BANKNIFTY 15m snapshots).

---

## 2. QUANTITATIVE MODEL ZERO-DRIFT ASSERTIONS

### A. Hawkes Process Intensity Invariance
- **Input:** Standard 100-bar tick volume array.
- **Assertion:** Hawkes baseline intensity $\lambda(t)$ must match baseline within absolute tolerance $\epsilon = 10^{-4}$.

### B. Kalman Filter & Particle Filter State Space Invariance
- **Input:** Standard OHLCV price series.
- **Assertion:** State estimation output $\hat{x}_t$ and particle mean price variance must match baseline within $\epsilon = 10^{-4}$.

### C. HMM Regime Detection Invariance
- **Input:** Standard multi-timeframe indicator matrix.
- **Assertion:** Current regime label (e.g. `TRENDING_BULL`) and regime probability distribution must match baseline **100% identically**.

### D. Bayesian Fusion & Probability Engine Invariance
- **Input:** Standard multi-stage outputs (Stages 1 through 7).
- **Assertion:** Final directional probabilities ($P_{\text{up}}, P_{\text{down}}, P_{\text{sideways}}$) and expected return must match baseline within $\epsilon = 10^{-4}$.

---

## 3. REST API SCHEMA BREAKING CHANGE PREVENTION

### Required Keys Assertion
Every `/api/dashboard/{symbol}` response must contain the following top-level keys without omission:
- `symbol`, `interval`, `timestamp`
- `prediction`: (`prediction_id`, `created_at`, `valid_until`, `prediction_state`, `signal`, `confidence`, `p_up`, `p_down`, `p_sideways`, `kelly_fraction`)
- `market_snapshot`: (`ltp`, `change_pct`, `rsi`, `macd`, `atr`, `ema9`, `ema21`, `ema50`, `volume`, `candle`, `supertrend`)
- `options_summary`: (`pcr`, `call_wall`, `put_wall`, `atm_iv`, `gamma_pressure`, `dealer_pressure`, `forecast`)
- `regime`: (`current`, `confidence`)

### Type Invariance Assertion
- Float fields must return valid Python floats or `null` (never `"NaN"`, `"Infinity"`, or stringified floats).
- Datetime fields must follow ISO 8601 string format (`YYYY-MM-DDTHH:MM:SS`).

---

## 4. BASELINE SPECIFICATION & MAINTENANCE

Golden reference files are stored in `tests/baselines/`:
- `nifty_15m_baseline.json`
- `banknifty_15m_baseline.json`

### Baseline Update Protocol
Golden baselines can **ONLY** be updated when a mathematical model version change is intentionally approved by the Quant Platform Architect. Updates are applied via:
```bash
python backend/tests/generate_baselines.py --update
```
