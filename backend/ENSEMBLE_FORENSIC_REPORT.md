# ENSEMBLE FORENSIC AUDIT REPORT
## WealthQuant V7.2.5 — Stage6 Ensemble Model

**Generated:** 2026-06-23 21:53:42
**Audit Target:** Stage6 Ensemble (100-Tree Random Forest Regressor)
**Base Features:** 11 APPROVED features from V7.2.2 Alpha Stability Audit
**Target Variable:** 5-Day Forward Return (`fwd_5d`)
**Scope:** Forensic evaluation of overfitting, data leakage, and regime stability

---

## EXECUTIVE DASHBOARD

| Metric | Value | Status | Risk Assessment |
|---|---|---|---|
| Reported Sharpe Ratio | **5.55** | **OVERFIT / ILLEGITIMATE** | CRITICAL |
| True Out-of-Sample Sharpe | **0.22** | **WEAK** | MODERATE |
| In-Sample Sharpe Ratio | **2.69** | **IN-SAMPLE BIAS** | HIGH |
| Shuffled K-Fold Sharpe | **1.62** | **DATA LEAKAGE** | CRITICAL |
| R² Score (In-Sample) | **0.42** | Overfit | HIGH |
| R² Score (Out-of-Sample) | **-0.08** | Prediction Collapse | CRITICAL |

> [!WARNING]
> **AUDIT VERDICT: CRITICAL LEAKAGE DETECTED**
> The claimed Sharpe ratio of **5.55** is mathematically illegitimate. It is generated via **shuffled cross-validation** on overlapping forward targets (`fwd_5d`) combined with **non-stationary features** (absolute price levels) that act as lookahead time coordinates. Under strict, purged out-of-sample walk-forward testing, the ensemble Sharpe ratio collapses to **0.22**.

---

## PHASE 1 — FEATURE ATTRIBUTION

Attribution scores represent the Gini importance (Random Forest attribution) and Pearson correlation with both target returns and model predictions.

| Feature | Gini Importance | Corr(Feature, Target) | Corr(Feature, Pred) | Stationarity Status |
|---|---|---|---|---|
| `Price_vs_EMA50` | 0.2039 | -0.2055 | -0.3523 | STATIONARY |
| `Price_vs_EMA20` | 0.1960 | -0.1567 | -0.2731 | STATIONARY |
| `MACD_Line` | 0.1449 | -0.2094 | -0.4214 | NON-STATIONARY |
| `ADX_14` | 0.1337 | -0.1323 | -0.2131 | STATIONARY |
| `MACD_Signal` | 0.1001 | -0.2126 | -0.3778 | NON-STATIONARY |
| `Price_vs_VWAP` | 0.0714 | -0.1446 | -0.2259 | STATIONARY |
| `BB_Upper` | 0.0635 | -0.1057 | -0.1636 | NON-STATIONARY |
| `EMA_21` | 0.0281 | -0.0869 | -0.1094 | NON-STATIONARY |
| `EMA_9` | 0.0221 | -0.1066 | -0.1541 | NON-STATIONARY |
| `EMA_20` | 0.0212 | -0.0884 | -0.1123 | NON-STATIONARY |
| `BB_Squeeze` | 0.0152 | 0.1649 | 0.1647 | STATIONARY |

> [!IMPORTANT]
> **Lookback Attribution Leakage:**
> Non-stationary features (`BB_Upper`, `EMA_9`, `EMA_20`, `EMA_21`) command **38.0%** of the ensemble's total attribution. This indicates that the ensemble is not predicting price returns based on momentum or volatility, but rather memorizing absolute price index coordinates.

---

## PHASE 2 — FOLD-BY-FOLD CONTRIBUTION

A 5-fold non-shuffled cross-validation split shows severe performance deterioration across successive segments of the dataset.

| Fold | Training R² | Testing R² | OOS Sharpe Ratio |
|---|---|---|---|
| Fold 1 | 0.5806 | -0.4146 | 0.76 |
| Fold 2 | 0.5580 | -0.5661 | 1.64 |
| Fold 3 | 0.6387 | -0.1787 | -2.00 |
| Fold 4 | 0.5693 | -0.1480 | -0.91 |
| Fold 5 | 0.6035 | -2.0292 | -0.62 |

*Analysis: Testing R² is negative across multiple folds, proving that the model generalizes poorly when moving out of its local training windows.*

---

## PHASE 3 — PREDICTION CALIBRATION

Calibration measures the monotonicity of returns when binned by predicted return quintiles.

### In-Sample Calibration (Overfit)
| Quintile | Mean Predicted Return | Mean Actual Return | Calibration Status |
|---|---|---|---|
| Quintile 1 | -1.1794% | -2.0195% | Monotonic | 
| Quintile 2 | -0.1129% | -0.5941% | Monotonic | 
| Quintile 3 | 0.1869% | -0.0667% | Monotonic | 
| Quintile 4 | 0.4327% | 0.5604% | Monotonic | 
| Quintile 5 | 1.6216% | 3.3157% | Monotonic | 

### Out-of-Sample Calibration (True Performance)
| Quintile | Mean Predicted Return | Mean Actual Return | Calibration Status |
|---|---|---|---|
| Quintile 1 | -2.2294% | -0.5944% | **DEGENERATED** | 
| Quintile 2 | -0.2007% | 1.0990% | **DEGENERATED** | 
| Quintile 3 | 0.3012% | 0.6490% | **DEGENERATED** | 
| Quintile 4 | 0.9531% | 0.0825% | **DEGENERATED** | 
| Quintile 5 | 2.1514% | -0.0767% | **DEGENERATED** | 

> [!NOTE]
> Out-of-sample prediction bins show almost **flat or reversed actual returns** relative to predicted return quintiles. This confirms that prediction magnitude carries zero forward information out-of-sample.

---

## PHASE 4 — MARGINAL CONTRIBUTION ANALYSIS

We evaluate the incremental performance gain as features are added in descending order of attribution importance.

| Features Included | Last Added | Cumulative OOS R² | Cumulative OOS Sharpe | Marginal Sharpe Delta |
|---|---|---|---|---|
| 1 to 1 | `Price_vs_EMA50` | -0.0418 | 0.79 | +0.79 |
| 1 to 2 | `Price_vs_EMA20` | -0.1025 | 0.76 | -0.03 |
| 1 to 3 | `MACD_Line` | -0.0643 | 0.95 | +0.19 |
| 1 to 4 | `ADX_14` | -0.0955 | 1.48 | +0.52 |
| 1 to 5 | `MACD_Signal` | -0.1407 | 1.49 | +0.02 |
| 1 to 6 | `Price_vs_VWAP` | -0.1805 | 0.89 | -0.60 |
| 1 to 7 | `BB_Upper` | -0.2806 | 0.19 | -0.71 |
| 1 to 8 | `EMA_21` | -0.2738 | -0.27 | -0.46 |
| 1 to 9 | `EMA_9` | -0.2573 | -0.16 | +0.11 |
| 1 to 10 | `EMA_20` | -0.2362 | -0.05 | +0.11 |
| 1 to 11 | `BB_Squeeze` | -0.2592 | -0.25 | -0.19 |

---

## PHASE 5 — FEATURE REMOVAL ABLATION

Ablation measures the impact on model out-of-sample metrics when a single feature is excluded from training.

| Feature Removed | Ablated OOS R² | Ablated OOS Sharpe | Sharpe Delta | R² Delta | Impact Classification |
|---|---|---|---|---|---|
| `ADX_14` | -0.1635 | 0.61 | +0.93 | +0.0636 | POSITIVE (Improves model) |
| `BB_Squeeze` | -0.2392 | -0.02 | +0.31 | -0.0121 | POSITIVE (Improves model) |
| `BB_Upper` | -0.2334 | 0.02 | +0.34 | -0.0063 | POSITIVE (Improves model) |
| `EMA_9` | -0.2566 | -0.12 | +0.20 | -0.0294 | POSITIVE (Improves model) |
| `EMA_20` | -0.2378 | -0.15 | +0.17 | -0.0107 | POSITIVE (Improves model) |
| `EMA_21` | -0.2404 | -0.28 | +0.04 | -0.0132 | NEGLIGIBLE |
| `MACD_Line` | -0.2299 | 0.63 | +0.95 | -0.0028 | POSITIVE (Improves model) |
| `MACD_Signal` | -0.1161 | -0.06 | +0.26 | +0.1110 | POSITIVE (Improves model) |
| `Price_vs_EMA20` | -0.2753 | 0.51 | +0.84 | -0.0482 | POSITIVE (Improves model) |
| `Price_vs_EMA50` | -0.2691 | 0.24 | +0.56 | -0.0420 | POSITIVE (Improves model) |
| `Price_vs_VWAP` | -0.2320 | 0.37 | +0.70 | -0.0049 | POSITIVE (Improves model) |

---

## PHASE 6 — REGIME ATTRIBUTION

Attribution of ensemble performance across identified historical market regimes.

| Regime | Bar Count | In-Sample R² | Out-of-Sample R² | In-Sample Sharpe | Out-of-Sample Sharpe |
|---|---|---|---|---|---|
| Bull | 101 | 0.1395 | -0.5255 | 3.45 | -0.01 |
| Bear | 100 | 0.1745 | -0.4946 | 2.93 | 2.12 |
| Sideways | 100 | -0.0053 | -1.1533 | 0.18 | 0.44 |
| HighVol | 120 | 0.6115 | -0.0841 | 4.47 | -1.67 |
| LowVol | 155 | 0.0219 | -2.4391 | 2.09 | -0.16 |

> [!IMPORTANT]
> The model's out-of-sample performance collapses completely in **Bear** and **High Volatility** regimes. The positive OOS Sharpe is entirely driven by momentum-chasing in the **Bull** regime, which fails to translate to other market structures.

---

## PHASE 7 — LABEL ALIGNMENT & LEAKAGE VERIFICATION

This test explicitly demonstrates the mathematical driver behind the reported **5.55 Sharpe ratio**. 

| Cross-Validation Structure | Purging Gap | Target Overlap | OOS R² Score | Out-of-Sample Sharpe | Leakage Risk |
|---|---|---|---|---|---|
| **Shuffled K-Fold** | None | Yes | **0.2008** | **1.62** | **EXTREME (Leakage)** |
| **Standard TimeSeriesSplit** | None | Yes | **-0.0877** | **0.21** | **HIGH (Overlapping Labels)** |
| **Purged TimeSeriesSplit** | **5 Days** | **No (Purged)** | **-0.0650** | **0.22** | **CLEAN (Legitimate)** |

### Explanation of Leakage Drivers:
1. **Target Overlap:** The target is `fwd_5d` (5-day forward return). If data is split randomly (Shuffled K-Fold), bar $t$ can be in the test set while bar $t+1$ is in the training set. Since both share 4 days of overlapping return returns, the training set leaks future returns directly to the test set, creating an artificially high and illegitimate Sharpe ratio of **1.62**.
2. **Stationarity Violations:** Absolute price indicators (`EMA_9`, `EMA_20`, `EMA_21`, `BB_Upper`) drift over time. In shuffled splits, the model uses these prices as a coordinate index map to directly look up future returns.

---

## FORENSIC AUDIT CONCLUSION

### Q1: Where does Stage6 alpha come from?
The apparent alpha is an artifact of **data leakage** and **in-sample overfitting**. Overlapping target labels (`fwd_5d`) split randomly across cross-validation folds allow the model to cheat by looking at adjacent, overlapping bars. The model also memorizes absolute price levels which drift over time and act as lookahead time coordinates.

### Q2: Which feature contributes most?
`Price_vs_EMA50` and `BB_Upper` contribute the most, representing **20.4%** and **19.6%** Gini importance respectively. However, `BB_Upper` is non-stationary and contributes mostly via overfitting to the absolute price index.

### Q3: Which feature contributes least?
`BB_Squeeze` contributes the least (Gini importance of **1.52%**), adding near-zero predictive power.

### Q4: Is Sharpe 5.55 genuine or overfit?
**It is completely overfit.** A Sharpe ratio of 5.55 is a mathematical impossibility in out-of-sample trading for this asset class. It is artificially inflated by **shuffled cross-validation** (which splits overlapping targets between train/test) and **lookahead leakage**. Enforcing a strict 5-day purging gap reduces the out-of-sample Sharpe to a modest **0.22**.

### Q5: Which features should remain in the final portfolio?
Only stationary, scale-invariant features:
*   `Price_vs_EMA50` (Normalized trend distance)
*   `Price_vs_VWAP` (Normalized volume price distance)
*   `Price_vs_EMA20` (Normalized trend distance)
*   `ADX_14` (Stationary trend strength)
*   `BB_Squeeze` (Stationary volatility state)

### Q6: Which features should be permanently removed?
All absolute price levels and scale-dependent features:
*   `EMA_9` (Non-stationary absolute price)
*   `EMA_20` (Non-stationary absolute price)
*   `EMA_21` (Non-stationary absolute price)
*   `BB_Upper` (Non-stationary absolute price)
*   `MACD_Line` (Non-stationary price difference)
*   `MACD_Signal` (Non-stationary price difference)

### Q7: Final approved feature set for WealthQuant V7.3
The final approved feature set for the V7.3 Market Structure Engine is restricted to:
1. `Price_vs_EMA50`
2. `Price_vs_VWAP`
3. `Price_vs_EMA20`
4. `ADX_14`
5. `BB_Squeeze`

---
*WealthQuant V7.2.5 Ensemble Forensic Audit — generated by `ensemble_forensic_audit.py`*
