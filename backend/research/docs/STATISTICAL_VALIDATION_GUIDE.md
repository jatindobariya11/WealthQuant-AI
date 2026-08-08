# Statistical Validation Guide

## 1. Information Coefficient (IC)
The Information Coefficient measures the rank correlation between predicted feature values and actual forward returns.
$$ IC = \rho_{spearman}(X, Y) $$
- **Spearman vs Pearson**: We exclusively use Spearman to mitigate the effect of outliers in financial data.
- **Thresholds**: IC > 0.03 (Good), IC > 0.05 (Excellent), IC > 0.10 (Holy Grail/Suspect Leakage).
- **t-statistic**: $t = IC \times \sqrt{N-2} / \sqrt{1 - IC^2}$

## 2. Walk-Forward Analysis
- **Purged k-fold**: Removes $k$ samples before and after the test set to prevent autocorrelation leakage.
- **Embargo**: A 5-day embargo period ensures structural non-overlap in overlapping return windows.
- **ICIR**: $ICIR = \mu(IC) / \sigma(IC)$. Target: > 0.5.

## 3. Monte Carlo Permutation Testing
- **Block Permutation**: Since financial time series exhibit serial correlation, simple shuffling destroys this structure. We use block permutations with block size $b=5$.
- **Benjamini-Hochberg**: $$ P_{(k)} \leq \frac{k}{m} \alpha $$ Used to control the False Discovery Rate (FDR) when evaluating multiple features.

## 4. Bootstrap Confidence Intervals
- **Circular Block Bootstrap**: Wraps the time series to ensure every observation has an equal chance of being sampled.
- **Block Length**: Selected via Politis-Romano algorithm (typically 5-10 days).
- **Requirement**: The 95% CI for the mean IC must strictly exclude zero.

## 5. Leakage Detection
- **IC Lag Test**: Compare $IC_{lag0}$ (using unlagged data) with $IC_{lag1}$.
- **Threshold**: If $IC_{lag0} / IC_{lag1} > 1.5$, leakage is suspected.
- **Classification**: CLEAN, SUSPECTED, CONFIRMED. Confirmed leakage results in immediate experiment rejection.

## 6. Population Stability Index (PSI)
$$ PSI = \sum (Actual\% - Expected\%) \times \ln\left(\frac{Actual\%}{Expected\%}\right) $$
- **Interpretation**: < 0.10 (Stable), 0.10-0.25 (Slight Shift), > 0.25 (Unstable/Regime Shift).

## 7. Kolmogorov-Smirnov Test
Used to test if feature distributions change between training and validation periods. High KS statistic indicates distribution drift.

## 8. Variance Inflation Factor (VIF)
$$ VIF_i = \frac{1}{1 - R_i^2} $$
- **Threshold**: VIF > 5 requires attention. VIF > 10 indicates severe multicollinearity; features must be orthogonalized or dropped.

## 9. Mutual Information
Captures non-linear dependencies between features and targets, whereas IC only captures monotonic relationships.

## 10. Ablation Study Protocol
- Iteratively nullify one feature at a time.
- Calculate overall model IC degradation.
- If degradation < 5%, feature is redundant.

## 11. Sensitivity Analysis
Vary hyper-parameters (e.g., rolling window size 10 to 30) and ensure the IC remains stable and statistically significant across the parameter grid.

## 12. Regime Stability Analysis
Calculate IC grouped by Market Regime (Bull, Bear, Sideways, High Vol). A robust feature should have positive IC in at least 70% of regimes.

## 13. Multiple Hypothesis Correction
- **Bonferroni**: Too conservative for highly correlated financial features.
- **Benjamini-Hochberg**: Standard for controlling FDR in WealthQuant research.
