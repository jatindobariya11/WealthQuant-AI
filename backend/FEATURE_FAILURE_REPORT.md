# FEATURE FAILURE REPORT
## WealthQuant V7.2.3 — Forensic Analysis of Rejected Features

**Generated:** 2026-06-21 15:35:33
**Source Audit:** WealthQuant V7.2.2 Alpha Stability Audit
**Features Under Autopsy:** 12

### Failure Taxonomy

| Code | Name | Description |
|---|---|---|
| `F1` | TIME_INSTABILITY | *See per-feature analysis below* |
| `F2` | REGIME_COLLAPSE | *See per-feature analysis below* |
| `F3` | ALPHA_DECAY | *See per-feature analysis below* |
| `F4` | SIGNAL_REVERSAL | *See per-feature analysis below* |
| `F5` | SPARSE_SIGNAL | *See per-feature analysis below* |
| `F6` | CORRELATION_COLLAPSE | *See per-feature analysis below* |
| `F7` | NaN_CONTAMINATION | *See per-feature analysis below* |
| `F8` | HORIZON_DRIFT | *See per-feature analysis below* |

### Repair Taxonomy

| Code | Label |
|---|---|
| `R1` | REPARABLE_CONDITIONING |
| `R2` | REPARABLE_NORMALIZATION |
| `R3` | REPARABLE_LOOKBACK |
| `R4` | REPARABLE_TRANSFORM |
| `R5` | REPARABLE_SPARSE_FIX |
| `R6` | PERMANENT_REJECT |
| `R7` | REGIME_SPECIFIC_ONLY |

---

## EXECUTIVE DASHBOARD

| Feature | Score | Decay | Stability | Primary Failure | Repair Code | Regime-Specific? | Permanent? |
|---|---|---|---|---|---|---|---|
| **ATR_14** | 28.9 | SIGNAL_REVERSAL | MODERATE | `F4` SIGNAL_REVERSAL | `R2` | NO | NO |
| **BB_Width** | 49.3 | SIGNAL_REVERSAL | MODERATE | `F4` SIGNAL_REVERSAL | `R4` | NO | NO |
| **Supertrend** | 4.0 | SIGNAL_REVERSAL | SIGN_FLIP | `F1` TIME_INSTABILITY | `R6` | NO | YES |
| **OBV** | 15.6 | SIGNAL_REVERSAL | SIGN_FLIP | `F1` TIME_INSTABILITY | `R4` | NO | NO |
| **RSI_Divergence** | 17.7 | SIGNAL_REVERSAL | MODERATE | `F2` REGIME_COLLAPSE | `R3` | NO | NO |
| **StochRSI_K** | 7.8 | SIGNAL_REVERSAL | SIGN_FLIP | `F1` TIME_INSTABILITY | `R3` | NO | YES |
| **Gap_Up** | 10.8 | SIGNAL_REVERSAL | SIGN_FLIP | `F1` TIME_INSTABILITY | `R1` | NO | YES |
| **Gap_Down** | 23.0 | SIGNAL_REVERSAL | MODERATE | `F2` REGIME_COLLAPSE | `R1` | NO | YES |
| **Hammer** | 25.0 | SIGNAL_REVERSAL | SIGN_FLIP | `F5` SPARSE_SIGNAL | `R5` | NO | NO |
| **Shooting_Star** | 25.0 | SIGNAL_REVERSAL | SIGN_FLIP | `F5` SPARSE_SIGNAL | `R5` | NO | NO |
| **Vol_Ratio** | 9.3 | SIGNAL_REVERSAL | SIGN_FLIP | `F1` TIME_INSTABILITY | `R6` | NO | YES |
| **Vol_Surge** | 23.9 | SATURATION | SIGN_FLIP | `F1` TIME_INSTABILITY | `R6` | NO | YES |

**Summary:** 12 features analysed — 6 permanently rejected, 6 reparable, 0 regime-specific candidates

---

## PER-FEATURE FORENSIC AUTOPSY

### ATR_14
**Category:** Volatility &nbsp;|&nbsp; **V7.2.2 Score:** 28.9/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 2.2%

#### Q1: Why Was It Rejected?

- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.108), np.float64(-0.15), np.float64(-0.126), np.float64(0.003), np.float64(0.116), np.float64(0.048)]

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.0199 | 0.7864 | 187 |
| Period_B | -0.1813 | 0.0102 | 200 |
| Period_C | -0.0101 | 0.8891 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | -0.1359 | 0.1628 | 107 | WEAK |
| Bear | -0.1547 | 0.1243 | 100 | WEAK |
| Sideways | -0.4593 | 0.0 | 100 | SIGNIFICANT |
| HighVol | -0.2346 | 0.0099 | 120 | SIGNIFICANT |
| LowVol | -0.1233 | 0.1265 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.1077 | 0.0093 | 582 |
| 10d | -0.1504 | 0.0003 | 577 |
| 20d | -0.1257 | 0.0027 | 567 |
| 30d | 0.0034 | 0.9362 | 557 |
| 60d | 0.1157 | 0.0078 | 527 |
| 90d | 0.0479 | 0.2862 | 497 |

**Signal Distribution:** CONTINUOUS — mean=356.2296, std=129.043, zero-pct=0.0%

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_NORMALIZATION**

**Repair Steps:**
- ATR normalized by price (ATR/Close*100) removes trending bias
- ATR-rank (rolling percentile) may stabilize directional IC
- Retest with ATR_Rank or ATR_Change as replacement signal

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: ['Bear', 'Sideways', 'HighVol']. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: HighVol, Sideways (as regime filter, not predictor)**
> Strongest regime: **Sideways** (r = -0.4593, p = 0.0, n = 100)


---

### BB_Width
**Category:** Volatility &nbsp;|&nbsp; **V7.2.2 Score:** 49.3/100 &nbsp;|&nbsp; **Grade:** D &nbsp;|&nbsp; **NaN Rate:** 3.2%

#### Q1: Why Was It Rejected?

- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.101), np.float64(-0.158), np.float64(-0.101), np.float64(0.009), np.float64(0.32), np.float64(0.085)]

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.2445 | 0.0009 | 181 |
| Period_B | -0.0865 | 0.2231 | 200 |
| Period_C | -0.0927 | 0.1974 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | -0.1402 | 0.162 | 101 | WEAK |
| Bear | -0.2996 | 0.0025 | 100 | SIGNIFICANT |
| Sideways | -0.1709 | 0.0892 | 100 | MARGINAL |
| HighVol | -0.2464 | 0.0067 | 120 | SIGNIFICANT |
| LowVol | -0.1942 | 0.0155 | 155 | SIGNIFICANT |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.1011 | 0.0152 | 576 |
| 10d | -0.1581 | 0.0001 | 571 |
| 20d | -0.1012 | 0.0165 | 561 |
| 30d | 0.0093 | 0.8269 | 551 |
| 60d | 0.32 | 0.0 | 521 |
| 90d | 0.0847 | 0.0608 | 491 |

**Signal Distribution:** CONTINUOUS — mean=7.2944, std=6.3659, zero-pct=0.0%

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_TRANSFORM**

**Repair Steps:**
- BB_Width_Rank (rolling percentile rank) removes trending bias
- BB_Width_Z (z-score) normalizes across regimes
- Use squeeze/expansion rate-of-change instead of raw width

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: ['Bear', 'Sideways', 'HighVol', 'LowVol']. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Bear, HighVol (expansion signals)**
> Strongest regime: **Bear** (r = -0.2996, p = 0.0025, n = 100)


---

### Supertrend
**Category:** Trend &nbsp;|&nbsp; **V7.2.2 Score:** 4.0/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 34.8%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(0.026), np.float64(nan)]
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.083), np.float64(-0.146), np.float64(-0.115), np.float64(-0.026), np.float64(0.02), np.float64(-0.092)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0062 — near-zero predictive correlation
- **`F7` — NaN_CONTAMINATION:** NaN rate = 34.8% — insufficient valid observations

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | None | None | 0 |
| Period_B | 0.0265 | 0.7162 | 191 |
| Period_C | nan | nan | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | None | None | 0 | INSUFFICIENT |
| Bear | nan | nan | 11 | WEAK |
| Sideways | nan | nan | 100 | WEAK |
| HighVol | -0.0134 | 0.8848 | 120 | WEAK |
| LowVol | nan | nan | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.0827 | 0.1049 | 386 |
| 10d | -0.1462 | 0.0042 | 381 |
| 20d | -0.1152 | 0.0265 | 371 |
| 30d | -0.0264 | 0.6169 | 361 |
| 60d | 0.0196 | 0.7229 | 331 |
| 90d | -0.0925 | 0.1094 | 301 |

**Signal Frequency:** BINARY — fires on 1847254.5% of bars (7222765 events in 391 bars)

#### Q2: Can It Be Repaired?

> **Verdict: NO — PERMANENT_REJECT**

**Repair Steps:**
- NaN contamination too severe — feature fires too rarely to repair

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Sign flip across time periods: [np.float64(0.026), np.float64(nan)].

#### Q4: Could It Become Regime-Specific?

> **NO — Regime-specific use not viable.** Correlation sign flips or signal is near-zero in every tested regime. No isolated regime provides consistent directional edge.


---

### OBV
**Category:** Volume &nbsp;|&nbsp; **V7.2.2 Score:** 15.6/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(-0.106), np.float64(-0.057), np.float64(0.002)]
- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(-0.53), 'Bear': np.float64(0.235), 'Sideways': np.float64(0.018), 'HighVol': np.float64(-0.123), 'LowVol': np.float64(-0.229)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.038), np.float64(-0.053), np.float64(-0.034), np.float64(-0.035), np.float64(0.091), np.float64(0.058)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0430 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.1065 | 0.1335 | 200 |
| Period_B | -0.0573 | 0.4205 | 200 |
| Period_C | 0.0022 | 0.9753 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | -0.5304 | 0.0 | 120 | SIGNIFICANT |
| Bear | 0.235 | 0.0186 | 100 | SIGNIFICANT |
| Sideways | 0.0178 | 0.8601 | 100 | WEAK |
| HighVol | -0.1233 | 0.1798 | 120 | WEAK |
| LowVol | -0.2291 | 0.0041 | 155 | SIGNIFICANT |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.0379 | 0.3558 | 595 |
| 10d | -0.0529 | 0.1998 | 590 |
| 20d | -0.0335 | 0.4208 | 580 |
| 30d | -0.035 | 0.4048 | 570 |
| 60d | 0.0909 | 0.0347 | 540 |
| 90d | 0.058 | 0.1913 | 510 |

**Signal Distribution:** CONTINUOUS — mean=8077855.085, std=6312222.088, zero-pct=0.2%

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_TRANSFORM**

**Repair Steps:**
- Use OBV_Signal = OBV minus OBV_EMA (removes trend drift)
- Rank OBV_Slope within rolling window for stationarity
- Test OBV divergence from price (separate from raw OBV level)

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: ['Bull', 'Bear', 'LowVol']. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Bull regime (r=-0.53 in Bull)**
> Strongest regime: **Bull** (r = -0.5304, p = 0.0, n = 120)


---

### RSI_Divergence
**Category:** Momentum &nbsp;|&nbsp; **V7.2.2 Score:** 17.7/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(0.128), 'Bear': np.float64(-0.049), 'Sideways': np.float64(-0.167), 'HighVol': np.float64(0.178), 'LowVol': np.float64(-0.09)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(0.046), np.float64(0.046), np.float64(0.06), np.float64(0.093), np.float64(-0.04), np.float64(-0.002)]

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | 0.0428 | 0.5472 | 200 |
| Period_B | 0.0835 | 0.2396 | 200 |
| Period_C | 0.0749 | 0.2982 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | 0.1275 | 0.1651 | 120 | WEAK |
| Bear | -0.0493 | 0.6264 | 100 | WEAK |
| Sideways | -0.1668 | 0.0972 | 100 | MARGINAL |
| HighVol | 0.1777 | 0.0522 | 120 | MARGINAL |
| LowVol | -0.0895 | 0.2681 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | 0.0459 | 0.2641 | 595 |
| 10d | 0.0457 | 0.2674 | 590 |
| 20d | 0.0595 | 0.1524 | 580 |
| 30d | 0.0934 | 0.0257 | 570 |
| 60d | -0.0403 | 0.3494 | 540 |
| 90d | -0.0019 | 0.9665 | 510 |

**Signal Distribution:** CONTINUOUS — mean=0.005, std=0.2417, zero-pct=94.2%

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_LOOKBACK**

**Repair Steps:**
- Test divergence strength (RSI_Div_Strength) vs binary flag
- Condition divergence on ADX > 25 (trending market confirmation)
- Test at longer lookbacks (20-bar window vs current 10-bar)

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: ['Sideways', 'HighVol']. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Bull, HighVol (r=0.13, 0.18)**
> Strongest regime: **HighVol** (r = 0.1777, p = 0.0522, n = 120)


---

### StochRSI_K
**Category:** Momentum &nbsp;|&nbsp; **V7.2.2 Score:** 7.8/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(-0.052), np.float64(0.036), np.float64(0.098)]
- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(-0.078), 'Bear': np.float64(0.023), 'Sideways': np.float64(0.149), 'HighVol': np.float64(0.109), 'LowVol': np.float64(-0.067)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(0.02), np.float64(0.051), np.float64(0.021), np.float64(-0.056), np.float64(-0.03), np.float64(-0.1)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0397 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.0525 | 0.4603 | 200 |
| Period_B | 0.0359 | 0.6136 | 200 |
| Period_C | 0.0977 | 0.1743 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | -0.0778 | 0.3983 | 120 | WEAK |
| Bear | 0.0228 | 0.8215 | 100 | WEAK |
| Sideways | 0.1487 | 0.1398 | 100 | WEAK |
| HighVol | 0.1091 | 0.2354 | 120 | WEAK |
| LowVol | -0.067 | 0.4077 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | 0.02 | 0.6259 | 595 |
| 10d | 0.0506 | 0.2197 | 590 |
| 20d | 0.0209 | 0.6158 | 580 |
| 30d | -0.0556 | 0.1853 | 570 |
| 60d | -0.03 | 0.4873 | 540 |
| 90d | -0.0995 | 0.0247 | 510 |

**Signal Distribution:** CONTINUOUS — mean=49.7021, std=34.901, zero-pct=13.2%

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_LOOKBACK**

**Repair Steps:**
- Use StochRSI smoothed EMA (removes noise)
- Test StochRSI momentum (change in K) instead of raw K
- Condition on Stochastic extreme zones (K < 10 or > 90)

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Sign flip across time periods: [np.float64(-0.052), np.float64(0.036), np.float64(0.098)].

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Sideways, HighVol (r=0.15, 0.11)**
> Strongest regime: **Sideways** (r = 0.1487, p = 0.1398, n = 100)


---

### Gap_Up
**Category:** Structure &nbsp;|&nbsp; **V7.2.2 Score:** 10.8/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(-0.06), np.float64(-0.039), np.float64(0.044)]
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.052), np.float64(-0.082), np.float64(-0.056), np.float64(-0.046), np.float64(0.028), np.float64(0.008)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0119 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.0598 | 0.4006 | 200 |
| Period_B | -0.0387 | 0.5869 | 200 |
| Period_C | 0.0443 | 0.5384 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | -0.0244 | 0.7913 | 120 | WEAK |
| Bear | -0.0444 | 0.6609 | 100 | WEAK |
| Sideways | -0.099 | 0.3269 | 100 | WEAK |
| HighVol | -0.0232 | 0.801 | 120 | WEAK |
| LowVol | -0.0469 | 0.5623 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.0525 | 0.2011 | 595 |
| 10d | -0.0822 | 0.046 | 590 |
| 20d | -0.0564 | 0.1749 | 580 |
| 30d | -0.0455 | 0.2784 | 570 |
| 60d | 0.0282 | 0.5136 | 540 |
| 90d | 0.0077 | 0.8617 | 510 |

**Signal Frequency:** BINARY — fires on 37.5% of bars (225 events in 600 bars)

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_CONDITIONING**

**Repair Steps:**
- Use Gap_Pct (continuous) instead of binary flag
- Condition on gap direction + Vol_Ratio > 1.5 confirmation
- Test gap-fill rate as separate predictive signal

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Sign flip across time periods: [np.float64(-0.06), np.float64(-0.039), np.float64(0.044)].

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Sideways (r=-0.10 for Gap_Up)**
> Strongest regime: **Sideways** (r = -0.099, p = 0.3269, n = 100)


---

### Gap_Down
**Category:** Structure &nbsp;|&nbsp; **V7.2.2 Score:** 23.0/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(0.002), 'Bear': np.float64(0.009), 'Sideways': np.float64(-0.064), 'HighVol': np.float64(0.019), 'LowVol': np.float64(0.033)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(0.036), np.float64(-0.022), np.float64(-0.02), np.float64(0.012), np.float64(0.09), np.float64(0.081)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0188 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | 0.0319 | 0.6537 | 200 |
| Period_B | 0.0043 | 0.9524 | 200 |
| Period_C | 0.031 | 0.6673 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | 0.0025 | 0.9782 | 120 | WEAK |
| Bear | 0.0092 | 0.9279 | 100 | WEAK |
| Sideways | -0.064 | 0.5271 | 100 | WEAK |
| HighVol | 0.0188 | 0.8387 | 120 | WEAK |
| LowVol | 0.0326 | 0.6872 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | 0.0365 | 0.3742 | 595 |
| 10d | -0.0217 | 0.5982 | 590 |
| 20d | -0.0199 | 0.633 | 580 |
| 30d | 0.0119 | 0.7771 | 570 |
| 60d | 0.0904 | 0.0356 | 540 |
| 90d | 0.0812 | 0.067 | 510 |

**Signal Frequency:** BINARY — fires on 33.5% of bars (201 events in 600 bars)

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_CONDITIONING**

**Repair Steps:**
- Use Gap_Pct (continuous) instead of binary flag
- Condition on gap direction + Vol_Ratio > 1.5 confirmation
- Test gap-fill rate as separate predictive signal

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Correlation sign inverts across regimes: {'Bull': np.float64(0.002), 'Bear': np.float64(0.009), 'Sideways': np.float64(-0.064), 'HighVol': np.float64(0.019), 'LowVol': np.float64(0.033)}.

#### Q4: Could It Become Regime-Specific?

> **YES — VIABLE_IN: Sideways (r=-0.10 for Gap_Up)**
> Strongest regime: **Sideways** (r = -0.064, p = 0.5271, n = 100)


---

### Hammer
**Category:** Candle &nbsp;|&nbsp; **V7.2.2 Score:** 25.0/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F5` — SPARSE_SIGNAL:** Binary signal fires only 0.0% of bars (0 total events)
- **`F8` — HORIZON_DRIFT:** IC direction drifts without commitment: [nan, nan, nan, nan, nan, nan]

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | nan | nan | 200 |
| Period_B | nan | nan | 200 |
| Period_C | nan | nan | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | nan | nan | 120 | WEAK |
| Bear | nan | nan | 100 | WEAK |
| Sideways | nan | nan | 100 | WEAK |
| HighVol | nan | nan | 120 | WEAK |
| LowVol | nan | nan | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | nan | nan | 595 |
| 10d | nan | nan | 590 |
| 20d | nan | nan | 580 |
| 30d | nan | nan | 570 |
| 60d | nan | nan | 540 |
| 90d | nan | nan | 510 |

**Signal Frequency:** BINARY — fires on 0.0% of bars (0 events in 600 bars)

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_SPARSE_FIX**

**Repair Steps:**
- Combine with confirming signal (e.g., Hammer + RSI_14 < 35)
- Use composite scoring instead of standalone binary signal
- Test on intraday data where frequency is higher

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: with significant transformation. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — POSSIBLY_IN_HIGH_VOL**
> Strongest regime: **Bull** (r = nan, p = nan, n = 120)


---

### Shooting_Star
**Category:** Candle &nbsp;|&nbsp; **V7.2.2 Score:** 25.0/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F5` — SPARSE_SIGNAL:** Binary signal fires only 0.0% of bars (0 total events)
- **`F8` — HORIZON_DRIFT:** IC direction drifts without commitment: [nan, nan, nan, nan, nan, nan]

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | nan | nan | 200 |
| Period_B | nan | nan | 200 |
| Period_C | nan | nan | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | nan | nan | 120 | WEAK |
| Bear | nan | nan | 100 | WEAK |
| Sideways | nan | nan | 100 | WEAK |
| HighVol | nan | nan | 120 | WEAK |
| LowVol | nan | nan | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | nan | nan | 595 |
| 10d | nan | nan | 590 |
| 20d | nan | nan | 580 |
| 30d | nan | nan | 570 |
| 60d | nan | nan | 540 |
| 90d | nan | nan | 510 |

**Signal Frequency:** BINARY — fires on 0.0% of bars (0 events in 600 bars)

#### Q2: Can It Be Repaired?

> **Verdict: YES — REPARABLE_SPARSE_FIX**

**Repair Steps:**
- Combine with confirming signal (e.g., Hammer + RSI_14 < 35)
- Use composite scoring instead of standalone binary signal
- Test on intraday data where frequency is higher

#### Q3: Should It Remain Rejected Permanently?

> **NO — Conditional Reprieve.** Feature may have value in specific contexts: with significant transformation. Recommend re-audit after applying repair transformations.

#### Q4: Could It Become Regime-Specific?

> **YES — POSSIBLY_IN_HIGH_VOL**
> Strongest regime: **Bull** (r = nan, p = nan, n = 120)


---

### Vol_Ratio
**Category:** Volume &nbsp;|&nbsp; **V7.2.2 Score:** 9.3/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 3.2%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(-0.014), np.float64(-0.055), np.float64(0.026)]
- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(0.058), 'Bear': np.float64(-0.077), 'Sideways': np.float64(-0.24), 'HighVol': np.float64(0.014), 'LowVol': np.float64(-0.012)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.03), np.float64(-0.011), np.float64(0.002), np.float64(0.018), np.float64(-0.024), np.float64(-0.06)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0180 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | -0.0136 | 0.8555 | 181 |
| Period_B | -0.0549 | 0.4402 | 200 |
| Period_C | 0.0257 | 0.7216 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | 0.0578 | 0.5657 | 101 | WEAK |
| Bear | -0.0771 | 0.4457 | 100 | WEAK |
| Sideways | -0.2404 | 0.016 | 100 | SIGNIFICANT |
| HighVol | 0.0144 | 0.8761 | 120 | WEAK |
| LowVol | -0.0121 | 0.8816 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.0297 | 0.4769 | 576 |
| 10d | -0.0109 | 0.7957 | 571 |
| 20d | 0.0017 | 0.9688 | 561 |
| 30d | 0.0175 | 0.6824 | 551 |
| 60d | -0.0235 | 0.5929 | 521 |
| 90d | -0.0602 | 0.1832 | 491 |

**Signal Distribution:** CONTINUOUS — mean=0.9963, std=0.4889, zero-pct=0.0%

#### Q2: Can It Be Repaired?

> **Verdict: NO — PERMANENT_REJECT**

**Repair Steps:**
- IC reversal across horizons indicates structural noise, not signal
- Feature direction depends entirely on horizon — unpredictable
- No lookback or normalization fix resolves directional ambiguity

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Sign flip across time periods: [np.float64(-0.014), np.float64(-0.055), np.float64(0.026)].

#### Q4: Could It Become Regime-Specific?

> **NO — Regime-specific use not viable.** Correlation sign flips or signal is near-zero in every tested regime. No isolated regime provides consistent directional edge.


---

### Vol_Surge
**Category:** Volume &nbsp;|&nbsp; **V7.2.2 Score:** 23.9/100 &nbsp;|&nbsp; **Grade:** F &nbsp;|&nbsp; **NaN Rate:** 0.0%

#### Q1: Why Was It Rejected?

- **`F1` — TIME_INSTABILITY:** Sign flip across time periods: [np.float64(0.039), np.float64(-0.074), np.float64(-0.051)]
- **`F2` — REGIME_COLLAPSE:** Correlation sign inverts across regimes: {'Bull': np.float64(0.114), 'Bear': np.float64(-0.115), 'Sideways': np.float64(-0.183), 'HighVol': np.float64(-0.058), 'LowVol': np.float64(-0.014)}
- **`F4` — SIGNAL_REVERSAL:** IC crosses zero at longer horizon: [np.float64(-0.008), np.float64(0.028), np.float64(0.047), np.float64(0.034), np.float64(0.036), np.float64(-0.018)]
- **`F6` — CORRELATION_COLLAPSE:** Global Pearson |r|=0.0370 — near-zero predictive correlation

**Time Stability (Period A / B / C):**

| Period | Pearson r | p-value | n |
|---|---|---|---|
| Period_A | 0.039 | 0.5832 | 200 |
| Period_B | -0.0739 | 0.2985 | 200 |
| Period_C | -0.0506 | 0.4823 | 195 |

**Regime Stability (Pearson r vs 5d forward return):**

| Regime | r | p-value | n | Significance |
|---|---|---|---|---|
| Bull | 0.1135 | 0.2172 | 120 | WEAK |
| Bear | -0.1149 | 0.2552 | 100 | WEAK |
| Sideways | -0.1826 | 0.0691 | 100 | MARGINAL |
| HighVol | -0.0579 | 0.5302 | 120 | WEAK |
| LowVol | -0.0141 | 0.8619 | 155 | WEAK |

**Information Coefficient (IC) Across Horizons:**

| Horizon | IC (Spearman r) | p-value | n |
|---|---|---|---|
| 5d | -0.008 | 0.8466 | 595 |
| 10d | 0.0278 | 0.5009 | 590 |
| 20d | 0.0467 | 0.262 | 580 |
| 30d | 0.0337 | 0.4215 | 570 |
| 60d | 0.0364 | 0.3984 | 540 |
| 90d | -0.0176 | 0.6924 | 510 |

**Signal Frequency:** BINARY — fires on 13.8% of bars (83 events in 600 bars)

#### Q2: Can It Be Repaired?

> **Verdict: NO — PERMANENT_REJECT**

**Repair Steps:**
- IC reversal across horizons indicates structural noise, not signal
- Feature direction depends entirely on horizon — unpredictable
- No lookback or normalization fix resolves directional ambiguity

#### Q3: Should It Remain Rejected Permanently?

> **YES — Permanently Rejected.** This feature has no viable repair path as a global alpha signal. Primary reason: Sign flip across time periods: [np.float64(0.039), np.float64(-0.074), np.float64(-0.051)].

#### Q4: Could It Become Regime-Specific?

> **NO — Regime-specific use not viable.** Correlation sign flips or signal is near-zero in every tested regime. No isolated regime provides consistent directional edge.


---

## COMPARATIVE FAILURE MATRIX

| Feature | F1 Time | F2 Regime | F3 Decay | F4 Reversal | F5 Sparse | F6 Corr | F7 NaN | Permanent |
|---|---|---|---|---|---|---|---|---|
| **ATR_14** | - | - | - | X | - | - | - | NO |
| **BB_Width** | - | - | - | X | - | - | - | NO |
| **Supertrend** | X | - | - | X | - | X | X | YES |
| **OBV** | X | X | - | X | - | X | - | NO |
| **RSI_Divergence** | - | X | - | X | - | - | - | NO |
| **StochRSI_K** | X | X | - | X | - | X | - | YES |
| **Gap_Up** | X | - | - | X | - | X | - | YES |
| **Gap_Down** | - | X | - | X | - | X | - | YES |
| **Hammer** | - | - | - | - | X | - | - | NO |
| **Shooting_Star** | - | - | - | - | X | - | - | NO |
| **Vol_Ratio** | X | X | - | X | - | X | - | YES |
| **Vol_Surge** | X | X | - | X | - | X | - | YES |

---

## REPAIR PRIORITY MATRIX

Features ranked by repair potential (highest first):

| Rank | Feature | Repair Code | Repair Label | Regime Viable | Recommended Action |
|---|---|---|---|---|---|
| 1 | **Gap_Up** | `R1` | REPARABLE_CONDITIONING | VIABLE_IN | Apply regime conditioning — re-audit in V7.3 |
| 2 | **Gap_Down** | `R1` | REPARABLE_CONDITIONING | VIABLE_IN | Apply regime conditioning — re-audit in V7.3 |
| 3 | **ATR_14** | `R2` | REPARABLE_NORMALIZATION | VIABLE_IN | Apply normalization — re-audit in V7.3 |
| 4 | **RSI_Divergence** | `R3` | REPARABLE_LOOKBACK | VIABLE_IN | Adjust lookback/parameters — re-audit in V7.3 |
| 5 | **StochRSI_K** | `R3` | REPARABLE_LOOKBACK | VIABLE_IN | Adjust lookback/parameters — re-audit in V7.3 |
| 6 | **BB_Width** | `R4` | REPARABLE_TRANSFORM | VIABLE_IN | Apply transform (rank/z-score/EMA) — re-audit in V7.3 |
| 7 | **OBV** | `R4` | REPARABLE_TRANSFORM | VIABLE_IN | Apply transform (rank/z-score/EMA) — re-audit in V7.3 |
| 8 | **Hammer** | `R5` | REPARABLE_SPARSE_FIX | POSSIBLY_IN_HIGH_VOL | Combine with other sparse signals — conditional only |
| 9 | **Shooting_Star** | `R5` | REPARABLE_SPARSE_FIX | POSSIBLY_IN_HIGH_VOL | Combine with other sparse signals — conditional only |
| 10 | **Supertrend** | `R6` | PERMANENT_REJECT | NOT_VIABLE | Permanently exclude — no viable repair path |
| 11 | **Vol_Ratio** | `R6` | PERMANENT_REJECT | NOT_VIABLE | Permanently exclude — no viable repair path |
| 12 | **Vol_Surge** | `R6` | PERMANENT_REJECT | NOT_VIABLE | Permanently exclude — no viable repair path |

---

## V7.3 DISPOSITION SUMMARY

### Features That Remain REJECTED for V7.3

- `Supertrend` — Sign flip across time periods: [np.float64(0.026), np.float64(nan)]
- `StochRSI_K` — Sign flip across time periods: [np.float64(-0.052), np.float64(0.036), np.float64(0.098)]
- `Gap_Up` — Sign flip across time periods: [np.float64(-0.06), np.float64(-0.039), np.float64(0.044)]
- `Gap_Down` — Correlation sign inverts across regimes: {'Bull': np.float64(0.002), 'Bear': np.float64(0.009), 'Sideways': np.float64(-0.064), 'HighVol': np.float64(0.019), 'LowVol': np.float64(0.033)}
- `Vol_Ratio` — Sign flip across time periods: [np.float64(-0.014), np.float64(-0.055), np.float64(0.026)]
- `Vol_Surge` — Sign flip across time periods: [np.float64(0.039), np.float64(-0.074), np.float64(-0.051)]

### Features Eligible for Conditional Re-entry (Post-Repair)

- `ATR_14` — REPARABLE_NORMALIZATION | Regime: VIABLE_IN: HighVol, Sideways (as regime filter, not predictor)
- `BB_Width` — REPARABLE_TRANSFORM | Regime: VIABLE_IN: Bear, HighVol (expansion signals)
- `OBV` — REPARABLE_TRANSFORM | Regime: VIABLE_IN: Bull regime (r=-0.53 in Bull)
- `RSI_Divergence` — REPARABLE_LOOKBACK | Regime: VIABLE_IN: Bull, HighVol (r=0.13, 0.18)
- `Hammer` — REPARABLE_SPARSE_FIX | Regime: POSSIBLY_IN_HIGH_VOL
- `Shooting_Star` — REPARABLE_SPARSE_FIX | Regime: POSSIBLY_IN_HIGH_VOL

### Regime-Specific Candidates (Gated Use)

*No features qualify for regime-specific use.*

---

## FINAL VERDICT

| Question | Answer |
|---|---|
| Why rejected? | Each feature fails on signal reversal, time instability, regime collapse, or NaN contamination — documented per-feature above |
| Can be repaired? | 9 of 12 features have conditional repair paths |
| Permanently rejected? | 6 features are permanently excluded as global signals |
| Regime-specific viable? | 0 features are viable when gated by regime classifier |

> **RULE: None of these REJECTED features may enter V7.3 Market Structure Engine**
> **without first completing their repair protocol and passing re-audit.**


---

*WealthQuant V7.2.3 Feature Failure Analysis — generated by `feature_failure_analysis.py`*
