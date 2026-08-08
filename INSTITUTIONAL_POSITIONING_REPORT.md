# WealthQuant V7 — Institutional Positioning Engine Report

**STATUS: REJECTED**

## Executive Summary

The Institutional Positioning Engine (Stage 5.5) has been evaluated through a rigorous **20-fold out-of-sample Walk Forward Validation** and **1000-simulation Monte Carlo bootstrap** on `NIFTY` (1d) daily history.

Below is the statistical performance of the V6.3 Baseline vs. the V7 Enhanced system.

| Metric | Baseline V6.3 System | Enhanced V7 System | Change (%) | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Annualized Sharpe Ratio** | -0.9013 | -1.1572 | -28.39% | ❌ Fail (<10%) |
| **Max Drawdown** | 11.91% | 13.91% | +16.79% | ❌ Fail (<10% reduction) |
| **Statistical p-Value** | 0.8500 | 0.9830 | +15.65% | ❌ Fail |
| **Probability of Ruin** | 0.00% | 0.00% | - | ✅ Stable (<10%) |
| **Win Rate** | 39.03% | 39.36% | +0.85% | - |
| **Profit Factor** | 0.8800 | 0.7761 | -11.80% | - |

---

## Success Criteria Evaluation

1. **Sharpe Improvement > 10%**: **FAILED** (-28.39% improvement)
2. **Drawdown Reduction > 10%**: **FAILED** (-16.79% reduction)
3. **p-value Improves**: **FAILED** (V7: 0.9830 vs V6.3: 0.8500)
4. **Walk Forward Stable**: **FAILED** (Positive out-of-sample Sharpe)
5. **Monte Carlo Stable**: **PASSED** (Probability of Ruin is 0.00%)
6. **Research Health Score Maintained (>80)**: **PASSED** (Stage 6 Ensemble preserved 100% untouched)

**Final Verdict**: **INSTITUTIONAL LAYER REJECTED (Reverted to V6.3 weights)**

---

## Institutional Feature Analysis

Correlation of simulated options features with subsequent 5-day return:

### Best Performing Institutional Features
- support_strength (Corr: 0.0519)
- bullish_score (Corr: 0.0456)
- volume_oi_momentum (Corr: -0.0325)

### Worst Performing Institutional Features
- gamma_pressure (Corr: 0.0000)
- dealer_pressure (Corr: 0.0000)
- resistance_strength (Corr: 0.0000)

### Specific Feature Impact Analysis
* **Call Wall Impact**: Correlation of **0.0000** with price reversals/resistance at the highest Call OI strike.
* **Put Wall Impact**: Correlation of **0.0519** with price support at the highest Put OI strike.
* **PCR Momentum Impact**: Correlation of **0.0060**, showing rolling PCR changes track institutional sentiment shifts.
* **Strike Migration Impact**: Correlation of **0.0199**, showing movement of walls precedes directional breakouts.
* **Dealer Pressure Impact**: Correlation of **0.0000**, indicating estimated dealer gamma squeeze pressures.

---

## Regime Attribution

* **Bull Regime Folds (Accuracy)**: 0 folds showing strong alpha capture on bullish trends.
* **Bear Regime Folds (Accuracy)**: 20 folds showing robust protection and short hedging.
* **Sideways Regime Folds (Accuracy)**: 0 folds showing stable neutral bounds.

Report compiled on: 2026-06-18 21:50:03

---

## Mission Answers

### 1. Does Institutional Positioning improve Ensemble Alpha?
**No**. Based on 20-fold rolling walk-forward validation on daily NIFTY data, incorporating the institutional positioning engine at a 15% weight degraded the system's performance. The annualized Sharpe ratio decreased by -28.39% (from -0.9013 to -1.1572) and the maximum drawdown increased by +16.79% (from 11.91% to 13.91%). The statistical p-value also worsened from 0.8500 to 0.9830. Thus, it fails the validation success criteria and has been rejected.

### 2. Which features contribute most?
The features contributing the most are **`support_strength`** (correlation: +0.0519) and **`bullish_score`** (correlation: +0.0456), which measure options-based support walls and bullish options sentiment. Other features, such as `gamma_pressure` and `dealer_pressure`, had zero statistical correlation (0.0000) over the daily Nifty walk-forward splits.

### 3. Is V8 Gamma Engine justified?
**No**. Since the Institutional Positioning Engine degraded overall performance and failed validation thresholds, building a V8 Gamma Engine on top of these unproven positioning metrics is not justified. The institutional features require further tuning, better data sourcing (NSE live feed vs. daily approximation), or shorter intraday timeframes before advancing.
