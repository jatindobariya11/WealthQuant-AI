# WealthQuant Quant Research Laboratory Manual

## 1. Introduction & Mission
### Research Philosophy
WealthQuant operates on a rigorous, hypothesis-driven quantitative research philosophy. We believe that true alpha is derived from fundamentally sound economic rationale, rigorously tested using institutional-grade statistical techniques, and protected from data leakage and overfitting.

### Laboratory Isolation Guarantee
The Research Laboratory is completely isolated from the Production Trading Engine. No data, state, or model weights can cross the boundary without passing through the strict Acceptance Gates.

### Research vs. Production Separation
- **Research**: Uses point-in-time historical data, operates asynchronously, focuses on statistical significance and predictive power (Information Coefficient).
- **Production**: Operates in real-time on live data streams, executes trades, focuses on latency, slippage, and portfolio PnL.

## 2. Research Laboratory Architecture
### Module Descriptions
1. `experiment.py`: Core experiment lifecycle management.
2. `hypothesis.py`: Statistical formulation of hypotheses.
3. `data_loader.py`: Historical point-in-time data access.
4. `feature_engineering.py`: Transformation of raw data into testable features.
5. `backtest.py`: Walk-forward validation and simulation.
6. `statistics.py`: IC calculation, permutations, bootstrap, and p-value generation.
7. `leakage.py`: Detection of look-ahead bias and autocorrelation.
8. `ablation.py`: Feature importance and redundancy checks.
9. `reporting.py`: Generation of standardized experiment reports.
10. `registry.py`: Database interaction for logging experiments.

### Database Tables Used
- `experiments`: Master table for all experiments.
- `hypotheses`: Logs of tested hypotheses.
- `experiment_results`: Detailed metrics per run.
- `features`: Feature definitions and versioning.

### Data Flow Diagram
```text
[Raw Data] --> [Data Loader (Point-in-Time)] --> [Feature Engineering]
                                                         |
[Hypothesis] --------------------------------------------+
                                                         |
                                                         v
                                              [Statistical Validation]
                                              (IC, WFA, Bootstrap)
                                                         |
                                                         v
[Production Candidate] <---(if passed)--- [Acceptance Gates / Health Score]
```

## 3. Research Categories
1. **Price Action**: Candlestick patterns, fractals. (IC Range: 0.02-0.05)
2. **Trend**: Moving averages, MACD. (IC Range: 0.01-0.04)
3. **Momentum**: RSI, ROC. (IC Range: 0.02-0.06)
4. **Volatility**: Historical vs Implied. (IC Range: 0.03-0.08)
5. **Options Flow**: Big trades, block sizes. (IC Range: 0.04-0.09)
6. **Open Interest**: OI changes, build-up. (IC Range: 0.03-0.07)
7. **PCR**: Put-Call Ratio dynamics. (IC Range: 0.02-0.06)
8. **Call Walls**: Highest call OI levels. (IC Range: 0.04-0.08)
9. **Put Walls**: Highest put OI levels. (IC Range: 0.04-0.08)
10. **Liquidity**: Bid-ask spread, depth. (IC Range: 0.01-0.05)
11. **Dealer Positioning**: Gamma exposure (GEX). (IC Range: 0.05-0.12)
12. **Institutional Positioning**: FII/DII data. (IC Range: 0.03-0.08)
13. **Market Microstructure**: Order flow imbalance. (IC Range: 0.04-0.10)
14. **Expiry Behaviour**: Pinning risk, theta decay. (IC Range: 0.06-0.15)
15. **Cross-Asset**: Currency, bonds correlation. (IC Range: 0.02-0.05)
16. **Calendar Effects**: Day of week, seasonality. (IC Range: 0.01-0.03)
17. **Regime Behaviour**: Bull vs Bear performance. (IC Range: 0.04-0.09)
18. **Risk Metrics**: VaR, Expected Shortfall. (IC Range: 0.02-0.05)
19. **Execution Quality**: Slippage predictors. (IC Range: 0.05-0.10)

## 4. Research Lifecycle
1. Idea Generation
2. Hypothesis Formulation
3. Feature Engineering
4. Point-in-time Data Retrieval
5. Cross-sectional IC Calculation
6. Walk-Forward Backtesting
7. Leakage Detection
8. Monte Carlo Permutation
9. Bootstrap CI Generation
10. Ablation Study
11. Regime Stability Check
12. Multiple Hypothesis Correction
13. Explainability (SHAP)
14. Health Score Calculation
15. Production Candidate Promotion

*Failure Modes*: If p-value > 0.05, experiment is rejected. If Leakage detected, rejected.

## 5. Experiment Design Guidelines
- **Formulating H0/H1**: H0 always assumes no predictive power (IC = 0). H1 assumes IC > 0 or IC < 0.
- **Choosing Horizon**: 1-day for flow, 5-day for structural features, intraday for microstructure.
- **Avoiding Pitfalls**: Always shift predictive features by T+1 to avoid look-ahead bias.

## 6. Statistical Standards
- **Minimum Sample Size**: N > 1000 observations per regime.
- **p-value Threshold**: p < 0.01 for new features, p < 0.05 for variations.
- **IC Threshold**: Mean IC > 0.03.
- **ICIR Standard**: IC / standard deviation > 0.5.

## 7. Acceptance Gate Specification
1. Mean IC > 0.03
2. IC p-value < 0.01
3. Bootstrap lower bound > 0
4. Walk-forward ICIR > 0.5
5. Leakage ratio (IC_lag0 / IC_lag1) < 1.5
6. Autocorrelation (lag 1) < 0.2
7. Max Drawdown in WFA < 15%
8. Regime consistency (positive IC in >70% regimes)
9. VIF < 5 (no multicollinearity)

*Health Score Formula*: Weighted sum of IC, ICIR, p-value rank, and robustness metrics out of 100.
*Immediate Rejection*: Any data leakage detected.

## 8. Reporting Standards
- Executive Summary
- Statistical Results (Table)
- Regime Breakdown (Chart)
- Feature Importance
- Conclusion & Recommendation

## 9. Governance
- **Creators**: Any Quant Researcher.
- **Approvers**: Chief Research Officer (CRO) / Head of Quant.
- **Versioning**: All accepted features must be committed to `features_vX.Y.py`.
