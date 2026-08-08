# Research Pipeline Specification

## Stage 1: Idea Generation
- **Sources**: Academic journals, practitioner blogs, data mining anomalies.
- **Screening**: Ideas must have sound financial intuition before any code is written.
- **Documentation**: A 1-paragraph rationale in the experiment registry.

## Stage 2: Hypothesis Formulation
- **H0**: Feature $X$ has zero predictive power for forward returns $Y$.
- **H1**: Feature $X$ has statistically significant predictive power for $Y$.
- **Framework**: Spearman Rank Correlation (IC).
- **Effect Size**: Minimum expected IC > 0.03.

## Stage 3: Feature Engineering
- **Computation**: Features must be computed on a rolling basis.
- **Normalization**: Z-score cross-sectionally per timestamp.
- **Lag Enforcement**: All features must be lagged by at least 1 observation (T+1 alignment).

## Stage 4: Historical Replay
- **Data Isolation**: Strict use of point-in-time data lakes.
- **Backfill**: Survivorship bias free datasets only.
- **Alignment**: Timestamps must align precisely to exchange market hours.

## Stage 5: Backtesting
- **Walk-Forward**: 120 days train / 20 days validate / 5 days test.
- **Costs**: 5 bps per trade assumed transaction cost.
- **Benchmark**: Nifty 50 Buy & Hold or Equal Weight universe.

## Stage 6: Walk-Forward Validation
- **Purged k-fold**: Uses `PurgedKFold` with purging to prevent train-test contamination.
- **Embargo**: 5 trading days.
- **Folds**: Minimum 10 folds.
- **Aggregation**: Mean of out-of-sample fold ICs.

## Stage 7: Monte Carlo Permutation
- **Method**: Block permutation of target variables.
- **Block Size**: 5 (to account for weekly expiry cycles).
- **Permutations**: n=1000.
- **Correction**: Benjamini-Hochberg for multiple hypothesis correction.

## Stage 8: Bootstrap
- **Method**: Circular block bootstrap on returns.
- **Samples**: 1000 samples, block=5.
- **CI**: 95% Confidence Interval. Lower bound must exclude zero.

## Stage 9: Ablation Study
- **Process**: Iteratively remove features from multi-factor models.
- **Metric**: Measure degradation in overall IC.
- **Redundancy**: If IC drops by < 5%, the feature is redundant.

## Stage 10: Explainability
- **SHAP**: Compute SHAP values for model attributions.
- **Ranking**: Feature importance ranking based on mean absolute SHAP.
- **Temporal SHAP**: Analyze how feature importance drifts over time.

## Stage 11: Research Health Score
$$ Score = (w_1 \times IC_{norm}) + (w_2 \times ICIR_{norm}) + (w_3 \times Pval_{norm}) - (w_4 \times Leakage_{penalty}) $$
- **Threshold**: Minimum 90/100 for acceptance.

## Stage 12: Accept/Reject Decision
- Must pass all 9 gates defined in the Quant Manual.
- **No Majority Vote**: All statistical gates are absolute mandates.
- **Exceptions**: Requires CRO sign-off with documented justification.

## Stage 13: Production Candidate
- **Integration**: Feature code integrated into IPS pipeline.
- **Versioning**: Assigned a semantic version (e.g., v2.1.0).
- **Monitoring**: Continuous out-of-sample monitoring in paper trading.
