# Hypothesis Catalog

This catalog outlines standard testable hypotheses across the 19 research categories.

## 1. Price Action
- **H_PA1**: `H0: Close-to-Close return has no relation to next day return.` | `H1: Mean reversion exists in 1-day returns.` | Expected IC: 0.02 | Horizon: 1D.
- **H_PA2**: `H0: Wick size is non-predictive.` | `H1: Large upper wicks predict negative forward returns.` | Expected IC: 0.03 | Horizon: 2D.

## 2. Trend
- **H_TR1**: `H0: 50/200 DMA crossover has no alpha.` | `H1: Golden cross predicts positive 20D returns.` | Expected IC: 0.01 | Horizon: 20D.
- **H_TR2**: `H0: ADX is not predictive.` | `H1: High ADX implies trend continuation.`

## 3. Momentum
- **H_MO1**: `H0: 14-day RSI is noise.` | `H1: RSI < 30 predicts mean reversion positive returns.`
- **H_MO2**: `H0: Rate of Change (ROC) has 0 IC.` | `H1: High ROC predicts momentum continuation over 5 days.`

## 4. Volatility
- **H_VO1**: `H0: IV Skew does not predict spot direction.` | `H1: High Put skew predicts spot decline.` | Expected IC: 0.06.
- **H_VO2**: `H0: Historical volatility is uncorrelated to forward returns.` | `H1: Low HV predicts volatility expansion breakouts.`

## 5. Options Flow
- **H_OF1**: `H0: Institutional block sizes are random.` | `H1: Unusually large call blocks predict spot rallies.`
- **H_OF2**: `H0: Option premium traded doesn't matter.` | `H1: Net premium imbalance predicts direction.`

## 6. Open Interest
- **H_OI1**: `H0: OI change is independent of price.` | `H1: Price up + OI up = Long buildup (Bullish).`
- **H_OI2**: `H0: OI velocity is noise.` | `H1: Rapid OI addition predicts imminent breakout.`

## 7. PCR (Put-Call Ratio)
- **H_PC1**: `H0: PCR is a random walk.` | `H1: Extreme high PCR acts as a contrarian bullish signal.`
- **H_PC2**: `H0: PCR momentum is zero.` | `H1: Rising PCR predicts bearish momentum.`

## 8. Call Walls
- **H_CW1**: `H0: Spot ignores Call Walls.` | `H1: High Call OI strikes act as resistance; spot returns mean-revert away.`

## 9. Put Walls
- **H_PW1**: `H0: Spot ignores Put Walls.` | `H1: High Put OI strikes act as support.`

## 10. Liquidity
- **H_LQ1**: `H0: Bid-Ask spread is not a factor.` | `H1: Widening spreads precede volatility shocks.`

## 11. Dealer Positioning
- **H_DP1**: `H0: GEX is irrelevant.` | `H1: Negative GEX predicts higher intraday realized volatility.`
- **H_DP2**: `H0: Zero Gamma level means nothing.` | `H1: Spot price acts like a magnet to Zero Gamma in low vol regimes.`

## 12. Institutional Positioning
- **H_IP1**: `H0: FII net long positioning is coincident.` | `H1: FII net long changes predict weekly returns.`
- **H_IP2**: `H0: DII vs FII divergence is noise.` | `H1: FII/DII divergence predicts regime shifts.`

## 13. Market Microstructure
- **H_MM1**: `H0: Order flow imbalance is zero-mean.` | `H1: Tick-level OFI predicts 5-min forward returns.`
- **H_MM2**: `H0: Trade sizes are uniform.` | `H1: High average trade size indicates informed flow.`

## 14. Expiry Behaviour
- **H_EB1**: `H0: Thursday expiry behaves like any day.` | `H1: Expiry day exhibits strong mean-reversion to Max Pain.`
- **H_EB2**: `H0: Theta decay is linear.` | `H1: Non-linear Thursday theta decay creates predictable premium crush.`

## 15. Cross-Asset
- **H_CA1**: `H0: USDINR does not impact Nifty.` | `H1: USDINR spikes negatively impact Nifty intraday.`
- **H_CA2**: `H0: US Yields don't drive Indian equities.` | `H1: US 10Y spikes correlate with Nifty gap-downs.`

## 16. Calendar Effects
- **H_CL1**: `H0: All days are equal.` | `H1: Monday mornings exhibit excess volatility.`
- **H_CL2**: `H0: Monthly boundaries are noise.` | `H1: Turn of month effect produces positive drift.`

## 17. Regime Behaviour
- **H_RG1**: `H0: Features perform equally in all regimes.` | `H1: Trend features perform poorly in High Vol regimes.`

## 18. Risk Metrics
- **H_RM1**: `H0: VaR breaches are random.` | `H1: Clustered VaR breaches predict structural market drawdowns.`

## 19. Execution Quality
- **H_EQ1**: `H0: Slippage is random.` | `H1: High short-term book imbalance predicts high execution slippage.`
