# Institutional Quant Research Best Practices

## 1. Hypothesis Design
- **Financial Intuition First**: Never mine data blindly. Every feature must have a logical reason why it should predict returns (e.g., "Dealers hedging negative gamma causes volatility").
- **Pre-registration**: Log the hypothesis *before* running the code to prevent HARKing (Hypothesizing After Results are Known).
- **Effect Size**: Estimate what a "good" result looks like before testing.

## 2. Data Handling
- **T+1 Lag Enforcement**: Always assume you cannot trade at the close of the signal day. Lag all features by 1 period.
- **Holidays & Expiries**: NSE holidays and Thursday (or weekly) expiries distort standard time series. Handle explicitly.
- **Split-Adjusted**: Ensure all price data is split and dividend-adjusted.

## 3. Feature Engineering
- **Normalization**: Cross-sectional Z-scoring is mandatory before IC calculation.
- **Winsorization**: Clip outliers at ±3σ to prevent extreme values from driving the correlation.
- **Rolling Windows**: Avoid arbitrary window sizes; test robustness across 10, 20, 50-day windows.

## 4. Statistical Testing
- **Significance**: Default $\alpha = 0.05$.
- **Two-Tailed Tests**: Always test for both positive and negative correlation.
- **MHC**: Apply Benjamini-Hochberg when testing multiple variations of a feature.

## 5. Walk-Forward Best Practices
- **Embargo**: Strict 5-day embargo between train and validation sets to kill autocorrelation.
- **Folds**: Minimum 10 folds for robust out-of-sample estimates.

## 6. Avoiding Overfitting
- **Occam's Razor**: Prefer simpler models with fewer parameters.
- **Deflated Sharpe Ratio**: Adjust expected performance based on the number of trials attempted (Bailey et al. 2014).

## 7. Reproducibility
- **Seeds**: Fix random seeds for all Monte Carlo and Bootstrap processes (`np.random.seed(42)`).
- **Versioning**: Code must be committed to git before an experiment is marked as COMPLETED.

## 8. Common Pitfalls
- **Survivorship Bias**: Especially in NSE stock data; ensure delisted stocks remain in historical universes.
- **Look-Ahead Bias**: Sneaking tomorrow's IV or closing price into today's feature.
- **Autocorrelation**: High IC but it's just predicting a highly autocorrelated target.

## 9. Research Ethics
- **Honest Reporting**: A failed experiment is valuable research. Do not hide negative results.
- **No Cherry-Picking**: Report the results of the exact parameters hypothesized, not the ones that happened to work best.
