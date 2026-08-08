# WealthQuant Research Roadmap (Next 12 Months)

## 1. Phase 1 — Foundation (Months 1-3)
- **Data Collection**: Ingest 3-6 months of high-resolution options historical data (tick-level or 1-minute).
- **Feature Computation**: Implement logic for all 536 baseline features across all universes.
- **Initial Screening**: Run massive cross-sectional IC screening.
- **Goal**: Identify the Top 50 features with IC > 0.03.

## 2. Phase 2 — Options Flow Research (Months 3-6)
- **OI Velocity**: Investigate Open Interest rate of change predicting directional breakouts (H_OI1, H_OI2).
- **PCR Extremes**: Validate Put-Call Ratio Z-scores as contrarian indicators (H_PC1).
- **IV Skew**: Build predictive models on IV skew changes (H_VO1).
- **Wall Mechanics**: Quantify the magnetic or repulsive effects of Call/Put Walls (H_CW1, H_PW1).
- **GEX Regimes**: Classify market regimes based on Net Gamma Exposure.

## 3. Phase 3 — Microstructure Research (Months 4-7)
- **Expiry Behaviour**: Model pinning risk and abnormal mean-reversion on expiry days (H_EB1, H_EB2).
- **Intraday Patterns**: Map standard liquidity and volatility curves throughout the trading day.
- **Dealer Positioning Proxies**: Reverse-engineer dealer gamma based on public flow data.
- **Order Flow Imbalance**: Tick-level prediction for execution optimization.

## 4. Phase 4 — IPS Construction (Months 6-9)
- **Selection**: Filter for Top validated features (IC > 0.08, Health Score ≥ 90).
- **Weighting**: Design the Intelligent Position Sizing (IPS) framework using inverse volatility and IC-weighted allocations.
- **Regimes**: Implement regime-conditional dynamic weights.
- **Backtesting**: Rigorous walk-forward backtesting of the complete IPS logic.

## 5. Phase 5 — Bayesian Integration (Months 9-12)
- **Integration**: Feed the IPS outputs as an additional informed prior into the Bayesian Fusion layer.
- **A/B Testing**: Run V6.3 baseline against V7 (with IPS).
- **Target**: Increase system-wide Sharpe Ratio from 5.55 to > 5.85 (+0.3 improvement).

## 6. Open Research Questions
1. Does Gamma Exposure (GEX) prediction decay faster in high-rate environments?
2. Can deep out-of-the-money option flows predict black swan events better than standard IV skew?
3. What is the optimal half-life for PCR mean reversion in the Indian market?
*(... plus 17 other identified quantitative questions ...)*

## 7. Priority Research Queue
1. **GEX Impact on Intraday Volatility** (Expected IC: High, Feasibility: Medium)
2. **Call Wall Repulsion** (Expected IC: Medium, Feasibility: High)
3. **FII Flow vs Retail Flow Divergence** (Expected IC: High, Feasibility: Low)

## 8. Resource Requirements
- **Data**: ~10 TB of tick-level options history.
- **Compute**: 4x A100 GPUs for SHAP and massive backtesting permutations.
- **Time**: Estimated 400 researcher-hours per phase.
