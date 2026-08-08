# WealthQuant Backtest Report

**Symbol:** BANKNIFTY | **Timeframe:** 15m | **Generated:** 2026-07-05 15:07:16 IST

**Data Source:** PostgreSQL (wealthquant) | **Mode:** Stored Predictions

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Initial Capital | INR 1.00 Cr |
| Final Equity | INR 99.57 L |
| Net Profit/Loss | 🔴 INR -42,798 (-0.43%) |
| Total Trades | 2 |
| Win Rate | 0.00% |
| Sharpe Ratio | -1.9205 |
| Max Drawdown | 0.43% |
| Data Quality | FAIL |

---

## 2. Performance Metrics

| Metric | Value |
|--------|-------|
| Total Trades | 2 |
| Win Rate | 0.00% |
| Loss Rate | 100.00% |
| Net Profit | INR -42,798 |
| Gross Profit | INR 0 |
| Gross Loss | INR 42,798 |
| Average Winner | INR 0 |
| Average Loser | INR 21,399 |
| Largest Winner | INR -715 |
| Largest Loser | INR -42,083 |
| Sharpe Ratio | -1.9205 |
| Sortino Ratio | -0.1033 |
| Profit Factor | 0.000 |
| Max Drawdown | 0.43% |
| Expectancy per Trade | INR -21,399 |
| Avg Holding (bars) | 3.0 |
| Risk/Reward Ratio | 0.000 |
| Consecutive Wins | 0 |
| Consecutive Losses | 2 |
| Total Return | -0.43% |
| Annualized Return | -1.54% |
| Transaction Costs | INR 799 |

---

## 3. Monthly Returns

| Month | Net P&L | Trades | Win Rate |
|-------|---------|--------|----------|
| 2026-06 | 🔴 INR -42,798 | 2 | 0.00% |

---

## 4. Equity Curve Summary

| | Value |
|---|---|
| Starting NAV | INR 1.00 Cr |
| Peak NAV | INR 1.00 Cr |
| Trough NAV | INR 99.57 L |
| Final NAV | INR 99.57 L |
| Total Bars | 1754 |
| Max Drawdown | 0.43% |

---

## 5. Regime Performance

| Regime | Trades | Win Rate | Net P&L | Profit Factor | Avg Hold |
|--------|--------|----------|---------|---------------|----------|
| TRENDING_BEAR | 2 | 0.00% | INR -42,798 | 0.000 | 3.0 bars |

---

## 6. Prediction Accuracy

| Metric | Value |
|--------|-------|
| Total Predictions Stored | 96 |
| Predictions Evaluated | 0 |
| Raw DB Accuracy | None% |
| Direction Correct (backtest) | 0 / 2 trades |
| Target Hit Rate | 0.0% |
| Stop Hit Rate | 50.0% |
| Avg MFE | 0.027% (6.6 pts) |
| Avg MAE | 29.285% (16989.77 pts) |
| Max MFE | 0.055% |
| Max MAE | 58.518% |

### Exit Reason Breakdown

| Exit Reason | Count | Win Rate | Net P&L |
|-------------|-------|----------|---------|
| STOP | 1 | 0.00% | INR -42,083 |
| TIME_EXIT | 1 | 0.00% | INR -715 |

---

## 7. Options Contribution Analysis

| Condition | Trades | Win Rate | Profit Factor |
|-----------|--------|----------|---------------|
| With Options Data | 2 | 0.00% | 0.0 |
| PCR 0.8-1.2 (Neutral) | 2 | 0.00% | 0.0 |
| Near Call Wall | 1 | 0.00% | 0.0 |
| ATM IV < 15% | 2 | 0.00% | 0.0 |
| FII Net Positive | 2 | 0.00% | N/A |
| DII Net Positive | 2 | 0.00% | N/A |

---

## 8. Best 5 Trades

| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |
|------------|--------|------|-------|------|-----|-------------|--------|
| 2026-06-29 04:16 | STRONG_BUY | BUY | 24,081.8 | 24,074.3 | 🟢 INR -715 | TIME_EXIT | TRENDING_BEAR |
| 2026-06-29 04:15 | STRONG_BUY | BUY | 58,045.4 | 55,593.1 | 🟢 INR -42,083 | STOP | TRENDING_BEAR |

## 9. Worst 5 Trades

| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |
|------------|--------|------|-------|------|-----|-------------|--------|
| 2026-06-29 04:16 | STRONG_BUY | BUY | 24,081.8 | 24,074.3 | 🔴 INR -715 | TIME_EXIT | TRENDING_BEAR |
| 2026-06-29 04:15 | STRONG_BUY | BUY | 58,045.4 | 55,593.1 | 🔴 INR -42,083 | STOP | TRENDING_BEAR |

---

## 10. Top Failure Reasons

| Regime | Losing Trades | Notes |
|--------|--------------|-------|
| TRENDING_BEAR | 2 (100.0%) | Worst performing regime |

### Losses by Exit Reason

| Exit Reason | Losing Trades | Total Loss |
|-------------|--------------|------------|
| STOP | 1 | INR -42,083 |
| TIME_EXIT | 1 | INR -715 |

---

## 11. Data Quality Report

**Overall Grade:** ❌ FAIL

| Check | Result |
|-------|--------|
| OHLCV Bars | 1814 |
| Date Range | 2025-12-29 to 2026-07-03 |
| Trading Days | 47 |
| Missing Candles | 55 |
| OHLCV Duplicates | 0 |
| Predictions Stored | 96 |
| Prediction Gaps | 64 |
| Options Coverage | 5.0% |
| FII/DII Coverage | 10.6% (5/47 days) |
| Raw DB Accuracy | None% |

**Issues Detected:**

- ⚠️ 55 candle gaps in BANKNIFTY 15m
- ⚠️ 64 predictions without OHLCV match
- ⚠️ Low options coverage: 5.0%
- ⚠️ Incomplete FII/DII: 5/47 days

---

## 12. Database Statistics

**Database:** PostgreSQL (wealthquant) | **Total Rows:** 10,508

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
| `backtests` | 1 |
| `prediction_results` | 0 |
| `alpha_leaderboard` | 0 |
| `feature_store` | 0 |
| `model_accuracy` | 0 |
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
| Particle | 51.6% | 0.0871 | 0.00228 | 1.1004 | HELPING |
| Meta Learning | 0.0% | 0.0 | 0.002058 | 0.0 | NEUTRAL |
| Institutional | 0.0% | 0.0 | 0.002058 | 0.0 | NEUTRAL |
| Kalman | 43.8% | -0.1283 | 0.009287 | -1.7989 | HURTING |
| Ensemble | 43.8% | -0.1339 | 216.780326 | -1.7989 | HURTING |
| Fusion | 40.6% | -0.2307 | 0.003781 | -3.3116 | HURTING |

---

*Report generated by WealthQuant Backtesting Engine — 2026-07-05 15:07:16 IST*
*All data sourced exclusively from PostgreSQL — zero external API calls.*