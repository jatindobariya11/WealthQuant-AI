# WealthQuant Backtest Report

**Symbol:** NIFTY | **Timeframe:** 15m | **Generated:** 2026-07-05 15:06:58 IST

**Data Source:** PostgreSQL (wealthquant) | **Mode:** Stored Predictions

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Initial Capital | INR 1.00 Cr |
| Final Equity | INR 1.06 Cr |
| Net Profit/Loss | 🟢 INR 6.46 L (+6.44%) |
| Total Trades | 18 |
| Win Rate | 27.78% |
| Sharpe Ratio | 2.1147 |
| Max Drawdown | 0.85% |
| Data Quality | FAIL |

---

## 2. Performance Metrics

| Metric | Value |
|--------|-------|
| Total Trades | 18 |
| Win Rate | 27.78% |
| Loss Rate | 72.22% |
| Net Profit | INR 6.46 L |
| Gross Profit | INR 8.29 L |
| Gross Loss | INR 1.83 L |
| Average Winner | INR 1.66 L |
| Average Loser | INR 14,095 |
| Largest Winner | INR 2.12 L |
| Largest Loser | INR -88,742 |
| Sharpe Ratio | 2.1147 |
| Sortino Ratio | 0.8262 |
| Profit Factor | 4.524 |
| Max Drawdown | 0.85% |
| Expectancy per Trade | INR 35,869 |
| Avg Holding (bars) | 3.3 |
| Risk/Reward Ratio | 11.761 |
| Consecutive Wins | 2 |
| Consecutive Losses | 6 |
| Total Return | 6.44% |
| Annualized Return | 12.04% |
| Transaction Costs | INR 7,764 |

---

## 3. Monthly Returns

| Month | Net P&L | Trades | Win Rate |
|-------|---------|--------|----------|
| 2026-06 | 🟢 INR 6.46 L | 16 | 25.00% |
| 2026-07 | 🟢 INR 143 | 2 | 50.00% |

---

## 4. Equity Curve Summary

| | Value |
|---|---|
| Starting NAV | INR 1.00 Cr |
| Peak NAV | INR 1.06 Cr |
| Trough NAV | INR 99.98 L |
| Final NAV | INR 1.06 Cr |
| Total Bars | 3458 |
| Max Drawdown | 0.85% |

---

## 5. Regime Performance

| Regime | Trades | Win Rate | Net P&L | Profit Factor | Avg Hold |
|--------|--------|----------|---------|---------------|----------|
| TRENDING_BULL | 1 | 0.00% | INR -1,894 | 0.000 | 5.0 bars |
| TRANSITION | 17 | 29.40% | INR 6.48 L | 4.571 | 3.2 bars |

---

## 6. Prediction Accuracy

| Metric | Value |
|--------|-------|
| Total Predictions Stored | 244 |
| Predictions Evaluated | 0 |
| Raw DB Accuracy | None% |
| Direction Correct (backtest) | 5 / 18 trades |
| Target Hit Rate | 27.8% |
| Stop Hit Rate | 38.9% |
| Avg MFE | 31.648% (7609.93 pts) |
| Avg MAE | 6.576% (3808.92 pts) |
| Max MFE | 142.444% |
| Max MAE | 58.701% |

### Exit Reason Breakdown

| Exit Reason | Count | Win Rate | Net P&L |
|-------------|-------|----------|---------|
| TIME_EXIT | 6 | 0.00% | INR -4,764 |
| TARGET | 5 | 100.00% | INR 8.29 L |
| STOP | 7 | 0.00% | INR -1.78 L |

---

## 7. Options Contribution Analysis

| Condition | Trades | Win Rate | Profit Factor |
|-----------|--------|----------|---------------|
| With Options Data | 17 | 29.40% | 4.571 |
| PCR 0.8-1.2 (Neutral) | 17 | 29.40% | 4.571 |
| ATM IV 15-25% | 17 | 29.40% | 4.571 |
| FII Net Positive | 5 | 0.00% | N/A |
| FII Net Negative | 2 | 50.00% | N/A |
| DII Net Positive | 7 | 14.30% | N/A |

---

## 8. Best 5 Trades

| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |
|------------|--------|------|-------|------|-----|-------------|--------|
| 2026-06-25 09:45 | STRONG_BUY | BUY | 24,052.8 | 28,997.7 | 🟢 INR 2.12 L | TARGET | TRANSITION |
| 2026-06-25 09:30 | STRONG_BUY | BUY | 24,055.3 | 28,996.6 | 🟢 INR 2.07 L | TARGET | TRANSITION |
| 2026-06-24 09:45 | BUY | BUY | 24,013.2 | 28,930.4 | 🟢 INR 2.06 L | TARGET | TRANSITION |
| 2026-06-24 09:30 | BUY | BUY | 24,006.5 | 28,948.3 | 🟢 INR 2.02 L | TARGET | TRANSITION |
| 2026-07-02 09:45 | STRONG_BUY | BUY | 24,168.0 | 24,211.2 | 🟢 INR 1,472 | TARGET | TRANSITION |

## 9. Worst 5 Trades

| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |
|------------|--------|------|-------|------|-----|-------------|--------|
| 2026-06-29 09:35 | STRONG_BUY | BUY | 23,949.8 | 23,932.0 | 🔴 INR -1,213 | STOP | TRANSITION |
| 2026-07-02 09:30 | STRONG_BUY | BUY | 24,175.8 | 24,155.5 | 🔴 INR -1,328 | STOP | TRANSITION |
| 2026-06-15 04:00 | STRONG_SELL | SELL | 23,964.8 | 24,001.2 | 🔴 INR -1,894 | TIME_EXIT | TRENDING_BULL |
| 2026-06-24 09:41 | BUY | BUY | 58,122.1 | 53,215.6 | 🔴 INR -83,792 | STOP | TRANSITION |
| 2026-06-25 09:41 | STRONG_BUY | BUY | 58,159.3 | 53,251.5 | 🔴 INR -88,742 | STOP | TRANSITION |

---

## 10. Top Failure Reasons

| Regime | Losing Trades | Notes |
|--------|--------------|-------|
| TRANSITION | 12 (92.3%) | Worst performing regime |
| TRENDING_BULL | 1 (7.7%) | Worst performing regime |

### Losses by Exit Reason

| Exit Reason | Losing Trades | Total Loss |
|-------------|--------------|------------|
| STOP | 7 | INR -1.78 L |
| TIME_EXIT | 6 | INR -4,764 |

---

## 11. Data Quality Report

**Overall Grade:** ❌ FAIL

| Check | Result |
|-------|--------|
| OHLCV Bars | 3518 |
| Date Range | 2026-03-19 to 2026-07-03 |
| Trading Days | 72 |
| Missing Candles | 80 |
| OHLCV Duplicates | 0 |
| Predictions Stored | 244 |
| Prediction Gaps | 187 |
| Options Coverage | 6.5% |
| FII/DII Coverage | 6.9% (5/72 days) |
| Raw DB Accuracy | None% |

**Issues Detected:**

- ⚠️ 80 candle gaps in NIFTY 15m
- ⚠️ 187 predictions without OHLCV match
- ⚠️ Low options coverage: 6.5%
- ⚠️ Incomplete FII/DII: 5/72 days

---

## 12. Database Statistics

**Database:** PostgreSQL (wealthquant) | **Total Rows:** 10,507

| Table | Rows |
|-------|------|
| `ohlcv_history` | 8,280 |
| `predictions` | 356 |
| `prediction_history` | 356 |
| `signal_explanations` | 356 |
| `regime_history` | 356 |
| `options_intelligence` | 333 |
| `walk_forward_results` | 242 |
| `feature_alpha_rankings` | 72 |
| `regime_performance` | 54 |
| `ablation_results` | 35 |
| `stage_contributions` | 30 |
| `experiments` | 16 |
| `feature_drift` | 10 |
| `prediction_accuracy` | 6 |
| `fii_dii` | 5 |
| `prediction_results` | 0 |
| `alpha_leaderboard` | 0 |
| `feature_store` | 0 |
| `model_accuracy` | 0 |
| `backtests` | 0 |
| `options_history` | 0 |
| `strike_history` | 0 |
| `wall_history` | 0 |
| `pcr_history` | 0 |

---

## 13. Walk-Forward Validation Summary

| Fold | Accuracy | F1 Score | Sharpe | Max Drawdown |
|------|----------|----------|--------|--------------|
| 20 | 24.2% | 0.2285 | -0.2593 | 2.09% |
| 19 | 35.8% | 0.3659 | -0.5695 | 0.69% |
| 18 | 30.5% | 0.3068 | -1.4963 | 0.94% |
| 17 | 27.4% | 0.2486 | -4.122 | 1.69% |
| 16 | 25.3% | 0.2509 | -0.8147 | 1.33% |
| 15 | 36.8% | 0.3342 | 1.2686 | 0.91% |
| 14 | 33.7% | 0.3272 | -1.5279 | 1.65% |
| 13 | 25.3% | 0.2354 | -2.2373 | 1.23% |
| 12 | 26.3% | 0.2627 | -0.1357 | 1.1% |
| 11 | 24.2% | 0.2265 | -2.4294 | 2.3% |
| 10 | 32.6% | 0.2733 | 0.4539 | 2.56% |
| 9 | 32.6% | 0.3129 | -0.387 | 0.95% |
| 8 | 29.5% | 0.2919 | -5.1546 | 2.91% |
| 7 | 28.4% | 0.2852 | -2.4816 | 2.0% |
| 6 | 27.4% | 0.2722 | 0.5737 | 0.9% |
| 5 | 42.1% | 0.3853 | -0.5944 | 0.55% |
| 4 | 25.3% | 0.2378 | -5.4662 | 2.11% |
| 3 | 31.6% | 0.2845 | -3.1641 | 1.27% |
| 2 | 34.7% | 0.3372 | -3.1909 | 1.36% |
| 1 | 32.6% | 0.3257 | -2.2983 | 1.45% |
| 20 | 28.4% | 0.2759 | 1.5162 | 1.56% |
| 19 | 37.9% | 0.3855 | -2.2411 | 1.46% |
| 18 | 32.6% | 0.3123 | -1.4161 | 0.9% |
| 17 | 32.6% | 0.3076 | -3.6204 | 1.57% |
| 16 | 26.3% | 0.2602 | -1.18 | 1.26% |
| 15 | 42.1% | 0.3612 | 1.2305 | 1.01% |
| 14 | 32.6% | 0.3156 | -1.7359 | 2.41% |
| 13 | 27.4% | 0.2617 | -2.9797 | 1.37% |
| 12 | 30.5% | 0.3037 | 0.1357 | 1.48% |
| 11 | 27.4% | 0.258 | -2.034 | 2.66% |
| 10 | 38.9% | 0.3067 | 0.91 | 2.56% |
| 9 | 35.8% | 0.3403 | 0.139 | 1.23% |
| 8 | 35.8% | 0.3578 | -2.0146 | 1.22% |
| 7 | 31.6% | 0.3159 | -0.753 | 1.32% |
| 6 | 27.4% | 0.2702 | -0.6359 | 0.97% |
| 5 | 42.1% | 0.3837 | -1.3136 | 0.9% |
| 4 | 21.1% | 0.1964 | -3.1158 | 1.25% |
| 3 | 32.6% | 0.2942 | -4.6809 | 1.84% |
| 2 | 34.7% | 0.3264 | -3.4177 | 1.64% |
| 1 | 30.5% | 0.3087 | -2.423 | 1.54% |
| 4 | 89.5% | 0.3148 | 0.0 | 0.0% |
| 3 | 83.2% | 0.369 | -0.0785 | 0.05% |
| 2 | 72.6% | 0.2805 | -3.6406 | 0.07% |
| 1 | 87.4% | 0.3109 | -2.4956 | 0.03% |
| 4 | 89.5% | 0.3148 | 0.0 | 0.0% |
| 3 | 82.1% | 0.3006 | -6.549 | 0.06% |
| 2 | 72.6% | 0.2805 | -3.6406 | 0.07% |
| 1 | 87.4% | 0.3109 | -2.4956 | 0.03% |
| 4 | 89.5% | 0.3148 | 0.0 | 0.0% |
| 3 | 80.0% | 0.2963 | -11.5338 | 0.08% |

---

## 14. Stage Contributions

| Stage | Accuracy | Correlation | MAE | Sharpe Contribution | Status |
|-------|----------|-------------|-----|---------------------|--------|
| Fusion | 57.7% | 0.0704 | 0.004043 | 2.1486 | HELPING |
| Particle | 61.3% | 0.4104 | 0.002698 | 1.9031 | HELPING |
| Ensemble | 57.1% | 0.1399 | 0.013109 | 1.8054 | HELPING |
| Meta Learning | 0.0% | 0.0 | 0.002626 | 0.0 | NEUTRAL |
| Institutional | 0.0% | 0.0 | 0.002626 | 0.0 | NEUTRAL |
| Kalman | 44.8% | -0.4164 | 0.013039 | -1.659 | HURTING |

---

*Report generated by WealthQuant Backtesting Engine — 2026-07-05 15:06:58 IST*
*All data sourced exclusively from PostgreSQL — zero external API calls.*