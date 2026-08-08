# FEATURE REPAIR REPORT
## WealthQuant V7.2.4 — Feature Repair Lab

**Generated:** 2026-06-21 17:33:43
**Source Audits:** V7.2.2 Alpha Stability Audit + V7.2.3 Feature Failure Analysis
**Pairs Evaluated:** 6 (Original vs Repaired)
**Target Variable:** 5-Day Forward Return (fwd_5d)
**Scope:** Research only — no Ensemble or Meta-Learning modifications

---

## REPAIR QUEUE

| Original Feature | Repaired Feature | Repair Protocol | Code | V7.2.2 Score |
|---|---|---|---|---|
| `ATR_14` | `ATR_Normalized` | ATR / Close * 100  →  removes absolute-price trending bias | `R2` | 28.9 |
| `BB_Width` | `ZScore_BB_Width` | Rolling 60-bar z-score of BB_Width  →  makes stationary, removes drift | `R4` | 49.3 |
| `OBV` | `Regime_OBV` | OBV_Signal = (OBV - EMA21_OBV) / ATR_proxy  →  detrended, normalized | `R4` | 15.6 |
| `RSI_Divergence` | `RSI_Div_ADX` | RSI_Divergence AND ADX > 25  →  gates divergence to confirmed trends only | `R3` | 17.7 |
| `Hammer` | `Hammer_RSI35` | Hammer AND RSI_14 < 35  →  gates to oversold reversals only | `R5` | 25.0 |
| `Shooting_Star` | `Star_RSI65` | Shooting_Star AND RSI_14 > 65  →  gates to overbought reversals only | `R5` | 25.0 |

---

## EXECUTIVE CLASSIFICATION

| Classification | Count | Features |
|---|---|---|
| PROMOTED | 0 | None |
| WATCHLIST | 0 | None |
| REJECTED | 6 | `ATR_Normalized`, `ZScore_BB_Width`, `Regime_OBV`, `RSI_Div_ADX`, `Hammer_RSI35`, `Star_RSI65` |

| Feature | Original Score | Repaired Score | Delta | Stability | Decay | Classification |
|---|---|---|---|---|---|---|
| `ATR_14` -> `ATR_Normalized` | 28.9 | 12.6 | -16.3 | SIGN_FLIP | SIGNAL_REVERSAL | REJECTED |
| `BB_Width` -> `ZScore_BB_Width` | 49.3 | 60.6 | +11.3 | STABLE | SIGNAL_REVERSAL | REJECTED |
| `OBV` -> `Regime_OBV` | 15.6 | 9.9 | -5.7 | SIGN_FLIP | SIGNAL_REVERSAL | REJECTED |
| `RSI_Divergence` -> `RSI_Div_ADX` | 17.7 | 22.7 | +5.0 | MODERATE | SIGNAL_REVERSAL | REJECTED |
| `Hammer` -> `Hammer_RSI35` | 25.0 | 25.0 | 0.0 | SIGN_FLIP | SIGNAL_REVERSAL | REJECTED |
| `Shooting_Star` -> `Star_RSI65` | 25.0 | 25.0 | 0.0 | SIGN_FLIP | SIGNAL_REVERSAL | REJECTED |

---

## PHASE 1 — REPAIR IMPLEMENTATIONS

### ATR_14 -> ATR_Normalized
**Category:** Volatility | **Repair Code:** `R2`
**Protocol:** ATR / Close * 100  →  removes absolute-price trending bias
**Original failure:** SIGNAL_REVERSAL — IC flips positive at 60d+ horizon

### BB_Width -> ZScore_BB_Width
**Category:** Volatility | **Repair Code:** `R4`
**Protocol:** Rolling 60-bar z-score of BB_Width  →  makes stationary, removes drift
**Original failure:** SIGNAL_REVERSAL — IC goes from -0.10 to +0.32 at 90d

### OBV -> Regime_OBV
**Category:** Volume | **Repair Code:** `R4`
**Protocol:** OBV_Signal = (OBV - EMA21_OBV) / ATR_proxy  →  detrended, normalized
**Original failure:** SIGN_FLIP — Bull r=-0.53 vs Bear r=+0.24

### RSI_Divergence -> RSI_Div_ADX
**Category:** Momentum | **Repair Code:** `R3`
**Protocol:** RSI_Divergence AND ADX > 25  →  gates divergence to confirmed trends only
**Original failure:** REGIME_COLLAPSE — direction flips in Sideways regime
**Signal frequency (original):** 19 events (3.2%)
**Signal frequency (repaired):** 7 events (1.2%)

### Hammer -> Hammer_RSI35
**Category:** Candle | **Repair Code:** `R5`
**Protocol:** Hammer AND RSI_14 < 35  →  gates to oversold reversals only
**Original failure:** SPARSE_SIGNAL — fires in 4.7% of bars with no oversold filter
**Signal frequency (original):** 0 events (0.0%)
**Signal frequency (repaired):** 0 events (0.0%)

### Shooting_Star -> Star_RSI65
**Category:** Candle | **Repair Code:** `R5`
**Protocol:** Shooting_Star AND RSI_14 > 65  →  gates to overbought reversals only
**Original failure:** SPARSE_SIGNAL — fires in 4.5% of bars with no overbought filter
**Signal frequency (original):** 0 events (0.0%)
**Signal frequency (repaired):** 0 events (0.0%)


---

## PHASE 2 — STABILITY AUDIT

*Period A = bars 1–200 | Period B = 201–400 | Period C = 401–600*

### ATR_14 vs ATR_Normalized

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `ATR_14` (original) | -0.0199 | -0.1813 | -0.0101 | 0.0785 | MODERATE |
| `ATR_Normalized` (repaired) | 0.0725 | -0.132 | 0.0544 | 0.0924 | SIGN_FLIP |

### BB_Width vs ZScore_BB_Width

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `BB_Width` (original) | -0.2445 | -0.0865 | -0.0927 | 0.073 | MODERATE |
| `ZScore_BB_Width` (repaired) | -0.2583 | -0.1461 | -0.1919 | 0.0461 | STABLE |

### OBV vs Regime_OBV

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `OBV` (original) | -0.1065 | -0.0573 | 0.0022 | 0.0444 | SIGN_FLIP |
| `Regime_OBV` (repaired) | -0.188 | 0.0867 | -0.0063 | 0.1141 | SIGN_FLIP |

### RSI_Divergence vs RSI_Div_ADX

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `RSI_Divergence` (original) | 0.0428 | 0.0835 | 0.0749 | 0.0175 | MODERATE |
| `RSI_Div_ADX` (repaired) | 0.0666 | 0.0102 | 0.2532 | 0.1038 | MODERATE |

### Hammer vs Hammer_RSI35

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `Hammer` (original) | nan | nan | nan | nan | SIGN_FLIP |
| `Hammer_RSI35` (repaired) | nan | nan | nan | nan | SIGN_FLIP |

### Shooting_Star vs Star_RSI65

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| `Shooting_Star` (original) | nan | nan | nan | nan | SIGN_FLIP |
| `Star_RSI65` (repaired) | nan | nan | nan | nan | SIGN_FLIP |


---

## PHASE 3 — REGIME AUDIT

*Pearson r against 5d forward return within each market regime.*

### ATR_14 vs ATR_Normalized

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `ATR_14` | -0.1359 | -0.1547 | -0.4593 | -0.2346 | -0.1233 | -0.2215 | 0.015631 | YES |
| `ATR_Normalized` | -0.0527 | -0.0644 | -0.4368 | -0.1711 | -0.105 | -0.166 | 0.020043 | YES |

### BB_Width vs ZScore_BB_Width

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `BB_Width` | -0.1402 | -0.2996 | -0.1709 | -0.2464 | -0.1942 | -0.2103 | 0.003203 | YES |
| `ZScore_BB_Width` | 0.5066 | -0.4638 | 0.1032 | -0.3106 | -0.1035 | -0.0536 | 0.11505 | NO |

### OBV vs Regime_OBV

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `OBV` | -0.5304 | 0.235 | 0.0178 | -0.1233 | -0.2291 | -0.126 | 0.065051 | NO |
| `Regime_OBV` | -0.3777 | 0.2096 | -0.0096 | -0.0024 | -0.213 | -0.0786 | 0.040225 | NO |

### RSI_Divergence vs RSI_Div_ADX

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `RSI_Divergence` | 0.1275 | -0.0493 | -0.1668 | 0.1777 | -0.0895 | -0.0001 | 0.01722 | NO |
| `RSI_Div_ADX` | 0.0952 | nan | -0.3854 | 0.1327 | nan | nan | nan | NO |

### Hammer vs Hammer_RSI35

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `Hammer` | nan | nan | nan | nan | nan | nan | nan | NO |
| `Hammer_RSI35` | nan | nan | nan | nan | nan | nan | nan | NO |

### Shooting_Star vs Star_RSI65

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar | Sign Consistent? |
|---|---|---|---|---|---|---|---|---|
| `Shooting_Star` | nan | nan | nan | nan | nan | nan | nan | NO |
| `Star_RSI65` | nan | nan | nan | nan | nan | nan | nan | NO |


---

## PHASE 4 — DECAY AUDIT

*Information Coefficient (Spearman r) at 5d / 10d / 20d / 30d / 60d / 90d.*

### ATR_14 vs ATR_Normalized

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `ATR_14` | -0.1077 | -0.1504 | -0.1257 | 0.0034 | 0.1157 | 0.0479 | 0.1504 | SIGNAL_REVERSAL |
| `ATR_Normalized` | -0.0818 | -0.123 | -0.0573 | 0.1038 | 0.2813 | 0.2068 | 0.2813 | SIGNAL_REVERSAL |

### BB_Width vs ZScore_BB_Width

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `BB_Width` | -0.1011 | -0.1581 | -0.1012 | 0.0093 | 0.32 | 0.0847 | 0.32 | SIGNAL_REVERSAL |
| `ZScore_BB_Width` | -0.1212 | -0.1844 | -0.2336 | -0.2293 | 0.2249 | 0.0839 | 0.2336 | SIGNAL_REVERSAL |

### OBV vs Regime_OBV

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `OBV` | -0.0379 | -0.0529 | -0.0335 | -0.035 | 0.0909 | 0.058 | 0.0909 | SIGNAL_REVERSAL |
| `Regime_OBV` | -0.0501 | -0.0396 | -0.1119 | -0.1924 | 0.0013 | 0.1334 | 0.1924 | SIGNAL_REVERSAL |

### RSI_Divergence vs RSI_Div_ADX

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `RSI_Divergence` | 0.0459 | 0.0457 | 0.0595 | 0.0934 | -0.0403 | -0.0019 | 0.0934 | SIGNAL_REVERSAL |
| `RSI_Div_ADX` | 0.0643 | 0.0091 | 0.0469 | 0.1306 | -0.019 | -0.0026 | 0.1306 | SIGNAL_REVERSAL |

### Hammer vs Hammer_RSI35

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `Hammer` | nan | nan | nan | nan | nan | nan | nan | SIGNAL_REVERSAL |
| `Hammer_RSI35` | nan | nan | nan | nan | nan | nan | nan | SIGNAL_REVERSAL |

### Shooting_Star vs Star_RSI65

| Feature | IC-5d | IC-10d | IC-20d | IC-30d | IC-60d | IC-90d | Max|IC| | Decay Type |
|---|---|---|---|---|---|---|---|---|
| `Shooting_Star` | nan | nan | nan | nan | nan | nan | nan | SIGNAL_REVERSAL |
| `Star_RSI65` | nan | nan | nan | nan | nan | nan | nan | SIGNAL_REVERSAL |


---

## PHASE 5 — HEAD-TO-HEAD COMPARISON

**Scoring:** Corr(20) + MI(15) + p-val(15) + Sample(10) + TimeStab(20) + RegimeStab(20) = 100

### ATR_14  vs  ATR_Normalized

| Metric | `ATR_14` (Original) | `ATR_Normalized` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 28.9 | 12.6 | -16.3 | `ATR_14` |
| Pearson r (global) | -0.0633 | -0.0187 | +0.0446 | `ATR_Normalized` |
| Correlation pts | 6.33 | 1.87 | -4.46 | `ATR_14` |
| Mutual Info pts | 5.55 | 5.7 | +0.15 | `ATR_Normalized` |
| p-value pts | 0.0 | 0.0 | 0.0 | TIE |
| Time Stab pts | 12.0 | 0.0 | -12.0 | `ATR_14` |
| Regime Stab pts | 10.0 | 10.0 | 0.0 | TIE |
| Corr Std (lower=better) | 0.0785 | 0.0924 | +0.0139 | `ATR_14` |
| Regime Variance (lower=better) | 0.0156 | 0.02 | +0.0044 | `ATR_14` |
| Max |IC| | 0.1504 | 0.2813 | +0.1309 | `ATR_Normalized` |

**Stability:** `ATR_14` → MODERATE | `ATR_Normalized` → SIGN_FLIP
**Decay:**     `ATR_14` → SIGNAL_REVERSAL | `ATR_Normalized` → SIGNAL_REVERSAL
**Delta Score:** -16.3

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons

### BB_Width  vs  ZScore_BB_Width

| Metric | `BB_Width` (Original) | `ZScore_BB_Width` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 49.3 | 60.6 | +11.3 | `ZScore_BB_Width` |
| Pearson r (global) | -0.0822 | -0.1595 | -0.0773 | `BB_Width` |
| Correlation pts | 8.22 | 15.95 | +7.73 | `ZScore_BB_Width` |
| Mutual Info pts | 7.24 | 4.65 | -2.59 | `BB_Width` |
| p-value pts | 10.0 | 15.0 | +5.0 | `ZScore_BB_Width` |
| Time Stab pts | 12.0 | 20.0 | +8.0 | `ZScore_BB_Width` |
| Regime Stab pts | 16.8 | 10.0 | -6.8 | `BB_Width` |
| Corr Std (lower=better) | 0.073 | 0.0461 | -0.0269 | `ZScore_BB_Width` |
| Regime Variance (lower=better) | 0.0032 | 0.115 | +0.1118 | `BB_Width` |
| Max |IC| | 0.32 | 0.2336 | -0.0864 | `BB_Width` |

**Stability:** `BB_Width` → MODERATE | `ZScore_BB_Width` → STABLE
**Decay:**     `BB_Width` → SIGNAL_REVERSAL | `ZScore_BB_Width` → SIGNAL_REVERSAL
**Delta Score:** 11.3

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons

### OBV  vs  Regime_OBV

| Metric | `OBV` (Original) | `Regime_OBV` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 15.6 | 9.9 | -5.7 | `OBV` |
| Pearson r (global) | 0.043 | 0.0127 | -0.0303 | `OBV` |
| Correlation pts | 4.3 | 1.27 | -3.03 | `OBV` |
| Mutual Info pts | 6.29 | 3.68 | -2.61 | `OBV` |
| p-value pts | 0.0 | 0.0 | 0.0 | TIE |
| Time Stab pts | 0.0 | 0.0 | 0.0 | TIE |
| Regime Stab pts | 10.0 | 10.0 | 0.0 | TIE |
| Corr Std (lower=better) | 0.0444 | 0.1141 | +0.0697 | `OBV` |
| Regime Variance (lower=better) | 0.0651 | 0.0402 | -0.0248 | `Regime_OBV` |
| Max |IC| | 0.0909 | 0.1924 | +0.1015 | `Regime_OBV` |

**Stability:** `OBV` → SIGN_FLIP | `Regime_OBV` → SIGN_FLIP
**Decay:**     `OBV` → SIGNAL_REVERSAL | `Regime_OBV` → SIGNAL_REVERSAL
**Delta Score:** -5.7

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons

### RSI_Divergence  vs  RSI_Div_ADX

| Metric | `RSI_Divergence` (Original) | `RSI_Div_ADX` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 17.7 | 22.7 | +5.0 | `RSI_Div_ADX` |
| Pearson r (global) | 0.0515 | 0.0506 | -0.0009 | `RSI_Divergence` |
| Correlation pts | 5.15 | 5.06 | -0.09 | `RSI_Divergence` |
| Mutual Info pts | 0.51 | 0.59 | +0.08 | `RSI_Div_ADX` |
| p-value pts | 0.0 | 0.0 | 0.0 | TIE |
| Time Stab pts | 12.0 | 12.0 | 0.0 | TIE |
| Regime Stab pts | 5.0 | 10.0 | +5.0 | `RSI_Div_ADX` |
| Corr Std (lower=better) | 0.0175 | 0.1038 | +0.0863 | `RSI_Divergence` |
| Regime Variance (lower=better) | 0.0172 | nan | nan | TIE |
| Max |IC| | 0.0934 | 0.1306 | +0.0372 | `RSI_Div_ADX` |

**Stability:** `RSI_Divergence` → MODERATE | `RSI_Div_ADX` → MODERATE
**Decay:**     `RSI_Divergence` → SIGNAL_REVERSAL | `RSI_Div_ADX` → SIGNAL_REVERSAL
**Delta Score:** 5.0

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons

### Hammer  vs  Hammer_RSI35

| Metric | `Hammer` (Original) | `Hammer_RSI35` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 25.0 | 25.0 | 0.0 | TIE |
| Pearson r (global) | nan | nan | nan | TIE |
| Correlation pts | 20.0 | 20.0 | 0.0 | TIE |
| Mutual Info pts | 0.0 | 0.0 | 0.0 | TIE |
| p-value pts | 0.0 | 0.0 | 0.0 | TIE |
| Time Stab pts | 0.0 | 0.0 | 0.0 | TIE |
| Regime Stab pts | 10.0 | 10.0 | 0.0 | TIE |
| Corr Std (lower=better) | nan | nan | nan | TIE |
| Regime Variance (lower=better) | nan | nan | nan | TIE |
| Max |IC| | nan | nan | nan | TIE |

**Stability:** `Hammer` → SIGN_FLIP | `Hammer_RSI35` → SIGN_FLIP
**Decay:**     `Hammer` → SIGNAL_REVERSAL | `Hammer_RSI35` → SIGNAL_REVERSAL
**Delta Score:** 0.0

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons

### Shooting_Star  vs  Star_RSI65

| Metric | `Shooting_Star` (Original) | `Star_RSI65` (Repaired) | Delta | Winner |
|---|---|---|---|---|
| Quality Score | 25.0 | 25.0 | 0.0 | TIE |
| Pearson r (global) | nan | nan | nan | TIE |
| Correlation pts | 20.0 | 20.0 | 0.0 | TIE |
| Mutual Info pts | 0.0 | 0.0 | 0.0 | TIE |
| p-value pts | 0.0 | 0.0 | 0.0 | TIE |
| Time Stab pts | 0.0 | 0.0 | 0.0 | TIE |
| Regime Stab pts | 10.0 | 10.0 | 0.0 | TIE |
| Corr Std (lower=better) | nan | nan | nan | TIE |
| Regime Variance (lower=better) | nan | nan | nan | TIE |
| Max |IC| | nan | nan | nan | TIE |

**Stability:** `Shooting_Star` → SIGN_FLIP | `Star_RSI65` → SIGN_FLIP
**Decay:**     `Shooting_Star` → SIGNAL_REVERSAL | `Star_RSI65` → SIGNAL_REVERSAL
**Delta Score:** 0.0

> **VERDICT: REJECTED**
> Signal reversal persists after repair — IC still crosses zero across horizons


---

## V7.3 INTEGRATION ELIGIBILITY

### Q1: Which repaired features survived?

*No repaired features survived the audit.*

### Q2: Which remain unstable?

**6 features remain unstable:**

- `ATR_Normalized` — Stability: SIGN_FLIP | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons
- `ZScore_BB_Width` — Stability: STABLE | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons
- `Regime_OBV` — Stability: SIGN_FLIP | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons
- `RSI_Div_ADX` — Stability: MODERATE | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons
- `Hammer_RSI35` — Stability: SIGN_FLIP | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons
- `Star_RSI65` — Stability: SIGN_FLIP | Decay: SIGNAL_REVERSAL | Signal reversal persists after repair — IC still crosses zero across horizons

### Q3: Which repaired features qualify for V7.3?

**No repaired features qualify for V7.3 in this audit cycle.**

> Recommendation: Features on WATCHLIST should complete further validation
> on live market data before V7.3 integration.

---

## AUDIT METRICS SUMMARY

| Metric | Value |
|---|---|
| Total Repair Pairs Evaluated | 6 |
| PROMOTED (V7.3 Eligible) | 0 |
| WATCHLIST (Needs Monitoring) | 0 |
| REJECTED (Repair Failed) | 6 |
| Average Score Improvement | +-0.9 |
| Best Repair | `BB_Width` -> `ZScore_BB_Width` (delta +11.3) |

> **RULE: ONLY PROMOTED features may enter V7.3 Market Structure Engine.**
> **WATCHLIST features require additional live-data validation.**

---

*WealthQuant V7.2.4 Feature Repair Lab — generated by `feature_repair_lab.py`*
