# ALPHA STABILITY REPORT
## WealthQuant V7.2.2 — Feature Alpha Rankings Audit

**Generated:** 2026-06-21 15:09:10
**Scope:** 55 features across 55 registered alpha signals
**Data:** 600 synthetic daily bars · 5 labelled regimes (Bull / Bear / Sideways / HighVol / LowVol)
**Target:** 5-Day Forward Return (fwd_5d)

---

## EXECUTIVE SUMMARY

| Classification | Count | % of Total |
|---|---|---|
| APPROVED | 11 | 20.0% |
| PROMISING | 9 | 16.4% |
| WATCHLIST | 13 | 23.6% |
| REJECT | 22 | 40.0% |
| **TOTAL** | **55** | **100%** |

---

## PHASE 1 — FEATURE DISCOVERY

| Category | Feature Count |
|---|---|
| Candle | 6 |
| Composite | 5 |
| Momentum | 5 |
| Strength | 4 |
| Structure | 8 |
| Trend | 15 |
| Volatility | 6 |
| Volume | 6 |

**55 features registered and discovered** across 7 indicator families.

---

## PHASE 2 — TIME STABILITY (Period A | B | C)

*History split into 3 equal periods of ~200 bars each.*

| Feature | Per-A r | Per-B r | Per-C r | Corr Std | Stability |
|---|---|---|---|---|---|
| ADX_14 | -0.2442 | -0.0468 | -0.3189 | 0.1148 | MODERATE |
| ADX_Trend_Strong | -0.2523 | -0.1099 | -0.1605 | 0.0589 | MODERATE |
| ATR_14 | -0.0199 | -0.1813 | -0.0101 | 0.0785 | MODERATE |
| BB_Lower | -0.3834 | -0.218 | -0.1808 | 0.0881 | MODERATE |
| BB_Position | -0.0459 | -0.0364 | 0.017 | 0.0277 | SIGN_FLIP |
| BB_Squeeze | 0.2399 | 0.2046 | 0.085 | 0.0663 | MODERATE |
| BB_Upper | -0.3813 | -0.2162 | -0.3335 | 0.0694 | STABLE |
| BB_Width | -0.2445 | -0.0865 | -0.0927 | 0.073 | MODERATE |
| Candle_Pattern | -0.0275 | -0.0684 | -0.0238 | 0.0202 | MODERATE |
| DI_Minus | -0.0384 | 0.126 | 0.1831 | 0.0939 | SIGN_FLIP |
| DI_Plus | -0.108 | -0.0212 | 0.0189 | 0.053 | SIGN_FLIP |
| Doji | 0.1003 | -0.0534 | 0.0096 | 0.0631 | SIGN_FLIP |
| EMA_20 | -0.3849 | -0.2852 | -0.4713 | 0.076 | STABLE |
| EMA_200 | -0.2162 | -0.0691 | -0.2132 | 0.0687 | MODERATE |
| EMA_20_50_Cross | -0.2026 | -0.1949 | 0.0746 | 0.1289 | SIGN_FLIP |
| EMA_21 | -0.3834 | -0.2827 | -0.4678 | 0.0756 | STABLE |
| EMA_50 | -0.3267 | -0.2013 | -0.3718 | 0.0721 | STABLE |
| EMA_9 | -0.3923 | -0.3087 | -0.4942 | 0.0758 | STABLE |
| EMA_9_20_Cross | -0.0877 | -0.0264 | -0.094 | 0.0305 | MODERATE |
| Gap_Down | 0.0319 | 0.0043 | 0.031 | 0.0128 | MODERATE |
| Gap_Up | -0.0598 | -0.0387 | 0.0443 | 0.0449 | SIGN_FLIP |
| HH_HL_Pattern | -0.0653 | -0.1413 | 0.0047 | 0.0596 | SIGN_FLIP |
| Hammer | nan | nan | nan | nan | SIGN_FLIP |
| LL_LH_Pattern | 0.0207 | 0.1165 | 0.067 | 0.0391 | MODERATE |
| Liquidity_Sweep | 0.0713 | -0.0121 | 0.0323 | 0.0341 | SIGN_FLIP |
| MACD_Crossover | 0.0844 | 0.0009 | 0.0221 | 0.0354 | MODERATE |
| MACD_Histogram | 0.0233 | -0.0801 | -0.0493 | 0.0433 | SIGN_FLIP |
| MACD_Line | -0.1641 | -0.272 | -0.2365 | 0.0449 | STABLE |
| MACD_Signal | -0.1899 | -0.2732 | -0.2408 | 0.0343 | STABLE |
| Market_Structure | -0.0465 | -0.1389 | -0.0369 | 0.046 | MODERATE |
| Marubozu_Bear | 0.0321 | 0.1266 | 0.0907 | 0.0389 | MODERATE |
| Marubozu_Bull | -0.0227 | 0.0465 | -0.0023 | 0.029 | SIGN_FLIP |
| Momentum_Rank | -0.0544 | -0.1339 | -0.0592 | 0.0364 | MODERATE |
| OBV | -0.1065 | -0.0573 | 0.0022 | 0.0444 | SIGN_FLIP |
| OBV_Slope | -0.127 | -0.007 | 0.0323 | 0.0678 | SIGN_FLIP |
| Price_vs_EMA20 | -0.1112 | -0.2435 | -0.1036 | 0.0642 | MODERATE |
| Price_vs_EMA50 | -0.1862 | -0.3256 | -0.1614 | 0.0723 | STABLE |
| Price_vs_VWAP | -0.2184 | -0.3944 | -0.3129 | 0.0719 | STABLE |
| RSI_14 | -0.075 | -0.154 | -0.0762 | 0.037 | MODERATE |
| RSI_Divergence | 0.0428 | 0.0835 | 0.0749 | 0.0175 | MODERATE |
| Regime_Bias | -0.0055 | -0.2135 | -0.1605 | 0.0883 | MODERATE |
| SR_Resistance | -0.3851 | -0.1863 | -0.3244 | 0.0832 | MODERATE |
| SR_Support | -0.3762 | -0.2911 | -0.1908 | 0.0758 | STABLE |
| Shooting_Star | nan | nan | nan | nan | SIGN_FLIP |
| Signal_Desk_Score | -0.0452 | -0.0589 | -0.018 | 0.017 | MODERATE |
| StochRSI_K | -0.0525 | 0.0359 | 0.0977 | 0.0616 | SIGN_FLIP |
| Stoch_D | 0.0191 | -0.0236 | 0.107 | 0.0544 | SIGN_FLIP |
| Stoch_K | -0.0285 | -0.0635 | 0.1105 | 0.0751 | SIGN_FLIP |
| Supertrend | None | 0.0265 | nan | nan | SIGN_FLIP |
| Supertrend_Dir | nan | -0.2045 | nan | nan | SIGN_FLIP |
| Technical_Score | -0.0804 | -0.0976 | 0.0054 | 0.045 | SIGN_FLIP |
| Trend_Score | -0.1646 | -0.1478 | -0.0133 | 0.0677 | MODERATE |
| VWAP | -0.2706 | -0.041 | -0.1675 | 0.0939 | MODERATE |
| Vol_Ratio | -0.0136 | -0.0549 | 0.0257 | 0.0329 | SIGN_FLIP |
| Vol_Surge | 0.039 | -0.0739 | -0.0506 | 0.0487 | SIGN_FLIP |

**Stability summary:** {'MODERATE': 23, 'SIGN_FLIP': 22, 'STABLE': 10}

---

## PHASE 3 — REGIME STABILITY

*Pearson r against 5d forward return within each market regime.*

| Feature | Bull | Bear | Sideways | HighVol | LowVol | AvgCorr | RegVar |
|---|---|---|---|---|---|---|---|
| ADX_14 | -0.2427 | -0.355 | 0.3014 | -0.23 | -0.2501 | -0.1553 | 0.054126 |
| ADX_Trend_Strong | -0.3521 | -0.0871 | 0.2945 | -0.246 | -0.0626 | -0.0906 | 0.04833 |
| ATR_14 | -0.1359 | -0.1547 | -0.4593 | -0.2346 | -0.1233 | -0.2215 | 0.015631 |
| BB_Lower | -0.4648 | -0.0101 | 0.098 | -0.0635 | -0.1217 | -0.1124 | 0.03628 |
| BB_Position | 0.0248 | -0.0892 | 0.0136 | -0.0144 | -0.1627 | -0.0456 | 0.005007 |
| BB_Squeeze | 0.1945 | 0.3804 | 0.0962 | 0.2632 | -0.0517 | 0.1765 | 0.021592 |
| BB_Upper | -0.3533 | -0.2836 | -0.1942 | -0.258 | -0.247 | -0.2672 | 0.002703 |
| BB_Width | -0.1402 | -0.2996 | -0.1709 | -0.2464 | -0.1942 | -0.2103 | 0.003203 |
| Candle_Pattern | -0.0207 | 0.0069 | 0.0427 | -0.1342 | 0.0826 | -0.0045 | 0.005407 |
| DI_Minus | -0.0721 | 0.232 | -0.3565 | 0.1862 | -0.011 | -0.0043 | 0.044164 |
| DI_Plus | -0.0262 | -0.1243 | 0.0399 | -0.1412 | -0.1878 | -0.0879 | 0.006858 |
| Doji | 0.1835 | -0.0238 | 0.0373 | -0.0168 | -0.1662 | 0.0028 | 0.012703 |
| EMA_20 | -0.3937 | -0.2371 | -0.1032 | -0.2302 | -0.2704 | -0.2469 | 0.008626 |
| EMA_200 | -0.3408 | -0.3699 | 0.3705 | -0.0477 | 0.0776 | -0.0621 | 0.075861 |
| EMA_20_50_Cross | -0.2957 | 0.0152 | -0.0423 | -0.2291 | 0.0084 | -0.1087 | 0.016587 |
| EMA_21 | -0.3934 | -0.2337 | -0.101 | -0.2266 | -0.2694 | -0.2448 | 0.008767 |
| EMA_50 | -0.3761 | -0.1688 | 0.1475 | -0.1473 | -0.2514 | -0.1592 | 0.029969 |
| EMA_9 | -0.3906 | -0.2601 | -0.0843 | -0.2678 | -0.2862 | -0.2578 | 0.009734 |
| EMA_9_20_Cross | -0.052 | -0.2256 | -0.1038 | -0.0539 | -0.1973 | -0.1265 | 0.005234 |
| Gap_Down | 0.0025 | 0.0092 | -0.064 | 0.0188 | 0.0326 | -0.0002 | 0.00112 |
| Gap_Up | -0.0244 | -0.0444 | -0.099 | -0.0232 | -0.0469 | -0.0476 | 0.000757 |
| HH_HL_Pattern | -0.0457 | -0.1375 | 0.0802 | -0.1321 | -0.194 | -0.0858 | 0.009138 |
| Hammer | nan | nan | nan | nan | nan | nan | nan |
| LL_LH_Pattern | 0.0072 | 0.101 | -0.1799 | 0.1395 | 0.1076 | 0.0351 | 0.013499 |
| Liquidity_Sweep | 0.0554 | -0.0436 | -0.0134 | 0.0855 | 0.1289 | 0.0425 | 0.004006 |
| MACD_Crossover | 0.0624 | -0.0625 | 0.0739 | 0.0594 | 0.014 | 0.0294 | 0.00253 |
| MACD_Histogram | 0.0493 | -0.0544 | 0.1378 | -0.0967 | 0.0933 | 0.0259 | 0.007817 |
| MACD_Line | -0.1094 | -0.2893 | -0.0728 | -0.3458 | -0.1555 | -0.1946 | 0.01109 |
| MACD_Signal | -0.1394 | -0.3374 | -0.1171 | -0.3581 | -0.1643 | -0.2232 | 0.0106 |
| Market_Structure | -0.0284 | -0.1293 | 0.1446 | -0.1386 | -0.176 | -0.0655 | 0.013424 |
| Marubozu_Bear | 0.0374 | -0.0026 | nan | 0.1393 | -0.0746 | nan | nan |
| Marubozu_Bull | 0.0056 | -0.0615 | 0.0281 | 0.0749 | 0.0195 | 0.0133 | 0.001941 |
| Momentum_Rank | 0.0545 | -0.1774 | 0.0435 | -0.1756 | -0.2105 | -0.0931 | 0.013634 |
| OBV | -0.5304 | 0.235 | 0.0178 | -0.1233 | -0.2291 | -0.126 | 0.065051 |
| OBV_Slope | -0.219 | 0.0438 | -0.0428 | 0.0103 | -0.1711 | -0.0758 | 0.010476 |
| Price_vs_EMA20 | -0.0465 | -0.1574 | 0.026 | -0.2362 | -0.1268 | -0.1082 | 0.008195 |
| Price_vs_EMA50 | -0.126 | -0.224 | -0.1014 | -0.3319 | -0.2743 | -0.2115 | 0.007602 |
| Price_vs_VWAP | -0.1213 | -0.2191 | -0.1628 | -0.3233 | -0.2417 | -0.2136 | 0.004791 |
| RSI_14 | 0.0262 | -0.1914 | 0.1404 | -0.2196 | -0.1838 | -0.0856 | 0.020476 |
| RSI_Divergence | 0.1275 | -0.0493 | -0.1668 | 0.1777 | -0.0895 | -0.0001 | 0.01722 |
| Regime_Bias | 0.0029 | -0.0871 | 0.2945 | -0.2823 | -0.0626 | -0.0269 | 0.034866 |
| SR_Resistance | -0.4058 | -0.1554 | -0.265 | -0.2387 | -0.2223 | -0.2574 | 0.006811 |
| SR_Support | -0.3959 | -0.0202 | 0.1275 | -0.1186 | -0.0182 | -0.0851 | 0.030319 |
| Shooting_Star | nan | nan | nan | nan | nan | nan | nan |
| Signal_Desk_Score | -0.0706 | -0.1365 | -0.0552 | -0.0303 | -0.0775 | -0.074 | 0.001238 |
| StochRSI_K | -0.0778 | 0.0228 | 0.1487 | 0.1091 | -0.067 | 0.0272 | 0.008278 |
| Stoch_D | 0.1451 | -0.0804 | 0.1139 | 0.0224 | -0.0385 | 0.0325 | 0.007442 |
| Stoch_K | 0.0642 | -0.0922 | 0.103 | -0.0041 | -0.0632 | 0.0015 | 0.005447 |
| Supertrend | None | None | nan | -0.0134 | nan | nan | nan |
| Supertrend_Dir | nan | -0.0001 | nan | nan | nan | nan | nan |
| Technical_Score | -0.136 | -0.1106 | -0.0858 | -0.0653 | -0.051 | -0.0897 | 0.000938 |
| Trend_Score | -0.1942 | -0.1164 | -0.0828 | -0.1613 | -0.1148 | -0.1339 | 0.001531 |
| VWAP | -0.3999 | -0.3082 | 0.3905 | -0.0102 | 0.0984 | -0.0459 | 0.081343 |
| Vol_Ratio | 0.0578 | -0.0771 | -0.2404 | 0.0144 | -0.0121 | -0.0515 | 0.010839 |
| Vol_Surge | 0.1135 | -0.1149 | -0.1826 | -0.0579 | -0.0141 | -0.0512 | 0.00997 |

---

## PHASE 4 — FEATURE DECAY TEST (30d / 60d / 90d)

*Information Coefficient (Spearman rank correlation) at increasing forward horizons.*

| Feature | IC-30d | IC-60d | IC-90d | Decay Type |
|---|---|---|---|---|
| ADX_14 | -0.3529 | -0.3974 | -0.1049 | MIXED |
| ADX_Trend_Strong | -0.1684 | -0.2096 | -0.0374 | MIXED |
| ATR_14 | -0.1257 | 0.0034 | 0.1157 | SIGNAL_REVERSAL |
| BB_Lower | -0.1588 | -0.1635 | -0.2755 | MIXED |
| BB_Position | -0.1498 | -0.2245 | -0.0825 | MIXED |
| BB_Squeeze | 0.3288 | 0.3856 | 0.0287 | MIXED |
| BB_Upper | -0.2401 | -0.2348 | -0.2259 | SATURATION |
| BB_Width | -0.1012 | 0.0093 | 0.32 | SIGNAL_REVERSAL |
| Candle_Pattern | 0.0363 | 0.0492 | 0.0684 | SATURATION |
| DI_Minus | 0.2053 | 0.3787 | 0.4682 | IMPROVING |
| DI_Plus | -0.0667 | -0.0534 | 0.1552 | SIGNAL_REVERSAL |
| Doji | -0.0195 | -0.0263 | 0.0043 | SIGNAL_REVERSAL |
| EMA_20 | -0.2013 | -0.2188 | -0.2143 | SATURATION |
| EMA_200 | -0.1099 | -0.1437 | -0.2193 | ALPHA_DECAY |
| EMA_20_50_Cross | -0.2607 | -0.2587 | -0.1678 | IMPROVING |
| EMA_21 | -0.1981 | -0.2148 | -0.2102 | SATURATION |
| EMA_50 | -0.1327 | -0.1435 | -0.169 | ALPHA_DECAY |
| EMA_9 | -0.2415 | -0.2687 | -0.2684 | MIXED |
| EMA_9_20_Cross | -0.2846 | -0.3238 | -0.1922 | MIXED |
| Gap_Down | -0.0199 | 0.0119 | 0.0904 | SIGNAL_REVERSAL |
| Gap_Up | -0.0564 | -0.0455 | 0.0282 | SIGNAL_REVERSAL |
| HH_HL_Pattern | -0.0855 | -0.1245 | 0.0003 | SIGNAL_REVERSAL |
| Hammer | nan | nan | nan | SIGNAL_REVERSAL |
| LL_LH_Pattern | 0.0999 | 0.1518 | 0.1172 | MIXED |
| Liquidity_Sweep | 0.0231 | 0.0346 | 0.0053 | MIXED |
| MACD_Crossover | -0.0632 | -0.1677 | -0.0881 | MIXED |
| MACD_Histogram | -0.0836 | -0.2114 | -0.1098 | MIXED |
| MACD_Line | -0.386 | -0.394 | -0.183 | MIXED |
| MACD_Signal | -0.4008 | -0.3563 | -0.1596 | IMPROVING |
| Market_Structure | -0.1023 | -0.1523 | -0.0651 | MIXED |
| Marubozu_Bear | 0.0315 | 0.0194 | 0.0206 | SATURATION |
| Marubozu_Bull | 0.0773 | 0.0744 | 0.0866 | SATURATION |
| Momentum_Rank | -0.216 | -0.2792 | -0.1305 | MIXED |
| OBV | -0.0335 | -0.035 | 0.0909 | SIGNAL_REVERSAL |
| OBV_Slope | -0.0008 | -0.0575 | 0.0001 | SIGNAL_REVERSAL |
| Price_vs_EMA20 | -0.2739 | -0.3116 | -0.1872 | MIXED |
| Price_vs_EMA50 | -0.3619 | -0.3779 | -0.1941 | MIXED |
| Price_vs_VWAP | -0.2197 | -0.2399 | -0.218 | MIXED |
| RSI_14 | -0.216 | -0.2792 | -0.1305 | MIXED |
| RSI_Divergence | 0.0595 | 0.0934 | -0.0403 | SIGNAL_REVERSAL |
| Regime_Bias | -0.2613 | -0.3514 | -0.1421 | MIXED |
| SR_Resistance | -0.2271 | -0.2219 | -0.2095 | SATURATION |
| SR_Support | -0.1692 | -0.2001 | -0.2721 | ALPHA_DECAY |
| Shooting_Star | nan | nan | nan | SIGNAL_REVERSAL |
| Signal_Desk_Score | -0.2532 | -0.3133 | -0.1901 | MIXED |
| StochRSI_K | 0.0209 | -0.0556 | -0.03 | SIGNAL_REVERSAL |
| Stoch_D | -0.0986 | -0.185 | -0.0268 | MIXED |
| Stoch_K | -0.103 | -0.1569 | -0.0265 | MIXED |
| Supertrend | -0.1152 | -0.0264 | 0.0196 | SIGNAL_REVERSAL |
| Supertrend_Dir | 0.0418 | 0.004 | 0.011 | MIXED |
| Technical_Score | -0.28 | -0.3308 | -0.2019 | MIXED |
| Trend_Score | -0.2794 | -0.3159 | -0.1826 | MIXED |
| VWAP | -0.1675 | -0.2083 | -0.3265 | ALPHA_DECAY |
| Vol_Ratio | 0.0017 | 0.0175 | -0.0235 | SIGNAL_REVERSAL |
| Vol_Surge | 0.0467 | 0.0337 | 0.0364 | SATURATION |

**Decay profile:** {'MIXED': 25, 'SIGNAL_REVERSAL': 15, 'IMPROVING': 3, 'SATURATION': 8, 'ALPHA_DECAY': 4}

---

## PHASE 5 — FEATURE QUALITY SCORES (0–100)

**Scoring:** Correlation (20) + Mutual Information (15) + p-value (15) + Sample Size (10) + Time Stability (20) + Regime Stability (20) = 100

| Feature | Score | Grade | Corr | MI | p-val | Sample | TStab | RStab |
|---|---|---|---|---|---|---|---|---|
| ADX_14 | 65.5 | B | 14.87 | 3.6 | 15.0 | 10.0 | 12.0 | 10.0 |
| ADX_Trend_Strong | 62.2 | C | 14.61 | 0.61 | 15.0 | 10.0 | 12.0 | 10.0 |
| ATR_14 | 28.9 | F | 6.33 | 5.55 | 0.0 | 10.0 | 12.0 | 10.0 |
| BB_Lower | 43.6 | D | 5.69 | 5.93 | 0.0 | 10.0 | 12.0 | 10.0 |
| BB_Position | 23.2 | F | 0.75 | 2.48 | 0.0 | 10.0 | 0.0 | 9.99 |
| BB_Squeeze | 65.1 | B | 16.96 | 1.14 | 15.0 | 10.0 | 12.0 | 10.0 |
| BB_Upper | 73.4 | B | 10.57 | 5.58 | 10.0 | 10.0 | 20.0 | 17.3 |
| BB_Width | 49.3 | D | 8.22 | 7.24 | 10.0 | 10.0 | 12.0 | 16.8 |
| Candle_Pattern | 38.3 | D | 4.59 | 2.15 | 0.0 | 10.0 | 12.0 | 9.59 |
| DI_Minus | 44.9 | D | 11.29 | 3.65 | 15.0 | 10.0 | 0.0 | 5.0 |
| DI_Plus | 12.5 | F | 0.09 | 4.24 | 0.0 | 10.0 | 0.0 | 13.14 |
| Doji | 0.4 | F | 0.11 | 0.26 | 0.0 | 10.0 | 0.0 | 5.0 |
| EMA_20 | 66.8 | B | 8.38 | 7.07 | 10.0 | 10.0 | 20.0 | 11.37 |
| EMA_200 | 34.8 | F | 4.11 | 6.73 | 0.0 | 10.0 | 12.0 | 10.0 |
| EMA_20_50_Cross | 33.1 | F | 7.28 | 0.86 | 5.0 | 10.0 | 0.0 | 10.0 |
| EMA_21 | 66.6 | B | 8.23 | 7.11 | 10.0 | 10.0 | 20.0 | 11.23 |
| EMA_50 | 45.6 | D | 5.64 | 7.94 | 0.0 | 10.0 | 20.0 | 10.0 |
| EMA_9 | 66.7 | B | 10.28 | 6.15 | 10.0 | 10.0 | 20.0 | 10.27 |
| EMA_9_20_Cross | 42.4 | D | 5.08 | 0.56 | 0.0 | 10.0 | 12.0 | 14.77 |
| Gap_Down | 23.0 | F | 1.88 | 0.22 | 0.0 | 10.0 | 12.0 | 13.88 |
| Gap_Up | 10.8 | F | 1.19 | 0.35 | 0.0 | 10.0 | 0.0 | 14.24 |
| HH_HL_Pattern | 12.9 | F | 6.66 | 0.39 | 0.0 | 10.0 | 0.0 | 10.86 |
| Hammer | 25.0 | F | 20.0 | 0.0 | 0.0 | 10.0 | 0.0 | 10.0 |
| LL_LH_Pattern | 39.1 | D | 6.95 | 0.16 | 5.0 | 10.0 | 12.0 | 5.0 |
| Liquidity_Sweep | 23.6 | F | 2.31 | 0.32 | 0.0 | 10.0 | 0.0 | 10.99 |
| MACD_Crossover | 37.6 | D | 2.7 | 0.4 | 0.0 | 10.0 | 12.0 | 12.47 |
| MACD_Histogram | 26.9 | F | 5.15 | 4.56 | 0.0 | 10.0 | 0.0 | 7.18 |
| MACD_Line | 79.7 | B | 20.0 | 4.7 | 15.0 | 10.0 | 20.0 | 10.0 |
| MACD_Signal | 79.6 | B | 20.0 | 4.62 | 15.0 | 10.0 | 20.0 | 10.0 |
| Market_Structure | 45.3 | D | 7.51 | 0.76 | 5.0 | 10.0 | 12.0 | 10.0 |
| Marubozu_Bear | 44.5 | D | 7.29 | 0.23 | 5.0 | 10.0 | 12.0 | 10.0 |
| Marubozu_Bull | 24.8 | F | 1.51 | 0.19 | 0.0 | 10.0 | 0.0 | 13.06 |
| Momentum_Rank | 41.1 | D | 6.54 | 2.6 | 0.0 | 10.0 | 12.0 | 10.0 |
| OBV | 15.6 | F | 4.3 | 6.29 | 0.0 | 10.0 | 0.0 | 10.0 |
| OBV_Slope | 8.9 | F | 1.26 | 2.67 | 0.0 | 10.0 | 0.0 | 10.0 |
| Price_vs_EMA20 | 68.3 | B | 15.52 | 3.98 | 15.0 | 10.0 | 12.0 | 11.81 |
| Price_vs_EMA50 | 81.0 | A | 20.0 | 3.56 | 15.0 | 10.0 | 20.0 | 12.4 |
| Price_vs_VWAP | 78.1 | B | 13.23 | 4.62 | 15.0 | 10.0 | 20.0 | 15.21 |
| RSI_14 | 53.0 | C | 8.4 | 2.6 | 10.0 | 10.0 | 12.0 | 10.0 |
| RSI_Divergence | 17.7 | F | 5.15 | 0.51 | 0.0 | 10.0 | 12.0 | 5.0 |
| Regime_Bias | 54.5 | C | 11.57 | 0.97 | 15.0 | 10.0 | 12.0 | 5.0 |
| SR_Resistance | 62.3 | C | 9.58 | 7.53 | 10.0 | 10.0 | 12.0 | 13.19 |
| SR_Support | 46.5 | D | 6.35 | 8.18 | 0.0 | 10.0 | 20.0 | 10.0 |
| Shooting_Star | 25.0 | F | 20.0 | 0.0 | 0.0 | 10.0 | 0.0 | 10.0 |
| Signal_Desk_Score | 46.6 | D | 2.98 | 2.85 | 0.0 | 10.0 | 12.0 | 18.76 |
| StochRSI_K | 7.8 | F | 3.97 | 2.16 | 0.0 | 10.0 | 0.0 | 6.72 |
| Stoch_D | 24.1 | F | 3.99 | 2.52 | 0.0 | 10.0 | 0.0 | 7.56 |
| Stoch_K | 23.4 | F | 1.42 | 2.45 | 0.0 | 10.0 | 0.0 | 9.55 |
| Supertrend | 4.0 | F | 0.62 | 1.43 | 0.0 | 7.0 | 0.0 | 10.0 |
| Supertrend_Dir | 24.5 | F | 3.43 | 1.07 | 0.0 | 10.0 | 0.0 | 10.0 |
| Technical_Score | 35.0 | D | 4.24 | 1.74 | 0.0 | 10.0 | 0.0 | 19.06 |
| Trend_Score | 48.8 | D | 5.75 | 2.55 | 0.0 | 10.0 | 12.0 | 18.47 |
| VWAP | 32.6 | F | 6.32 | 7.28 | 0.0 | 10.0 | 12.0 | 5.0 |
| Vol_Ratio | 9.3 | F | 1.8 | 2.54 | 0.0 | 10.0 | 0.0 | 10.0 |
| Vol_Surge | 23.9 | F | 3.7 | 0.22 | 0.0 | 10.0 | 0.0 | 10.03 |

**Portfolio Average Quality Score: 39.4 / 100**

---

## PHASE 6 — CLASSIFICATION

### APPROVED — Cleared for V7.3 Market Structure Engine

- **ADX_14** | Score: 65.5 | Grade: B | Score 65.5/100, time-stable [MODERATE], passes V7.3 criteria
- **BB_Squeeze** | Score: 65.1 | Grade: B | Score 65.1/100, time-stable [MODERATE], passes V7.3 criteria
- **BB_Upper** | Score: 73.4 | Grade: B | Score 73.4/100, time-stable [STABLE], passes V7.3 criteria
- **EMA_20** | Score: 66.8 | Grade: B | Score 66.8/100, time-stable [STABLE], passes V7.3 criteria
- **EMA_21** | Score: 66.6 | Grade: B | Score 66.6/100, time-stable [STABLE], passes V7.3 criteria
- **EMA_9** | Score: 66.7 | Grade: B | Score 66.7/100, time-stable [STABLE], passes V7.3 criteria
- **MACD_Line** | Score: 79.7 | Grade: B | Score 79.7/100, time-stable [STABLE], passes V7.3 criteria
- **MACD_Signal** | Score: 79.6 | Grade: B | Score 79.6/100, time-stable [STABLE], passes V7.3 criteria
- **Price_vs_EMA20** | Score: 68.3 | Grade: B | Score 68.3/100, time-stable [MODERATE], passes V7.3 criteria
- **Price_vs_EMA50** | Score: 81.0 | Grade: A | Score 81.0/100, time-stable [STABLE], passes V7.3 criteria
- **Price_vs_VWAP** | Score: 78.1 | Grade: B | Score 78.1/100, time-stable [STABLE], passes V7.3 criteria

### PROMISING — Monitor and Re-evaluate

- **ADX_Trend_Strong** | Score: 62.2 | Grade: C | Score 62.2/100 — shows alpha potential, more validation needed
- **EMA_50** | Score: 45.6 | Grade: D | Score 45.6/100 — shows alpha potential, more validation needed
- **Market_Structure** | Score: 45.3 | Grade: D | Score 45.3/100 — shows alpha potential, more validation needed
- **RSI_14** | Score: 53.0 | Grade: C | Score 53.0/100 — shows alpha potential, more validation needed
- **Regime_Bias** | Score: 54.5 | Grade: C | Score 54.5/100 — shows alpha potential, more validation needed
- **SR_Resistance** | Score: 62.3 | Grade: C | Score 62.3/100 — shows alpha potential, more validation needed
- **SR_Support** | Score: 46.5 | Grade: D | Score 46.5/100 — shows alpha potential, more validation needed
- **Signal_Desk_Score** | Score: 46.6 | Grade: D | Score 46.6/100 — shows alpha potential, more validation needed
- **Trend_Score** | Score: 48.8 | Grade: D | Score 48.8/100 — shows alpha potential, more validation needed

### WATCHLIST — Weak signal, keep monitoring

- **BB_Lower** | Score: 43.6 | Grade: D | Score 43.6/100 — weak alpha, keep under observation
- **Candle_Pattern** | Score: 38.3 | Grade: D | Score 38.3/100 — weak alpha, keep under observation
- **DI_Minus** | Score: 44.9 | Grade: D | Score 44.9/100 — weak alpha, keep under observation
- **EMA_200** | Score: 34.8 | Grade: F | Score 34.8/100 — weak alpha, keep under observation
- **EMA_20_50_Cross** | Score: 33.1 | Grade: F | Score 33.1/100 — weak alpha, keep under observation
- **EMA_9_20_Cross** | Score: 42.4 | Grade: D | Score 42.4/100 — weak alpha, keep under observation
- **LL_LH_Pattern** | Score: 39.1 | Grade: D | Score 39.1/100 — weak alpha, keep under observation
- **MACD_Crossover** | Score: 37.6 | Grade: D | Score 37.6/100 — weak alpha, keep under observation
- **MACD_Histogram** | Score: 26.9 | Grade: F | Score 26.9/100 — weak alpha, keep under observation
- **Marubozu_Bear** | Score: 44.5 | Grade: D | Score 44.5/100 — weak alpha, keep under observation
- **Momentum_Rank** | Score: 41.1 | Grade: D | Score 41.1/100 — weak alpha, keep under observation
- **Technical_Score** | Score: 35.0 | Grade: D | Score 35.0/100 — weak alpha, keep under observation
- **VWAP** | Score: 32.6 | Grade: F | Score 32.6/100 — weak alpha, keep under observation

### REJECT — Excluded from V7.3

- **ATR_14** | Score: 28.9 | Grade: F | Signal reversal — direction inverts at longer horizons
- **BB_Position** | Score: 23.2 | Grade: F | Score 23.2/100 — insufficient predictive power
- **BB_Width** | Score: 49.3 | Grade: D | Signal reversal — direction inverts at longer horizons
- **DI_Plus** | Score: 12.5 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Doji** | Score: 0.4 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Gap_Down** | Score: 23.0 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Gap_Up** | Score: 10.8 | Grade: F | Signal reversal — direction inverts at longer horizons
- **HH_HL_Pattern** | Score: 12.9 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Hammer** | Score: 25.0 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Liquidity_Sweep** | Score: 23.6 | Grade: F | Score 23.6/100 — insufficient predictive power
- **Marubozu_Bull** | Score: 24.8 | Grade: F | Score 24.8/100 — insufficient predictive power
- **OBV** | Score: 15.6 | Grade: F | Signal reversal — direction inverts at longer horizons
- **OBV_Slope** | Score: 8.9 | Grade: F | Signal reversal — direction inverts at longer horizons
- **RSI_Divergence** | Score: 17.7 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Shooting_Star** | Score: 25.0 | Grade: F | Signal reversal — direction inverts at longer horizons
- **StochRSI_K** | Score: 7.8 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Stoch_D** | Score: 24.1 | Grade: F | Score 24.1/100 — insufficient predictive power
- **Stoch_K** | Score: 23.4 | Grade: F | Score 23.4/100 — insufficient predictive power
- **Supertrend** | Score: 4.0 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Supertrend_Dir** | Score: 24.5 | Grade: F | Score 24.5/100 — insufficient predictive power
- **Vol_Ratio** | Score: 9.3 | Grade: F | Signal reversal — direction inverts at longer horizons
- **Vol_Surge** | Score: 23.9 | Grade: F | Score 23.9/100 — insufficient predictive power

---

## PHASE 7 — V7.3 INTEGRATION ELIGIBILITY

### Q1: Which features survive?

**20 features survive the audit** (APPROVED + PROMISING):

- `ADX_14` [APPROVED] · Score: 65.5 · Category: Strength
- `ADX_Trend_Strong` [PROMISING] · Score: 62.2 · Category: Strength
- `BB_Squeeze` [APPROVED] · Score: 65.1 · Category: Volatility
- `BB_Upper` [APPROVED] · Score: 73.4 · Category: Volatility
- `EMA_20` [APPROVED] · Score: 66.8 · Category: Trend
- `EMA_21` [APPROVED] · Score: 66.6 · Category: Trend
- `EMA_50` [PROMISING] · Score: 45.6 · Category: Trend
- `EMA_9` [APPROVED] · Score: 66.7 · Category: Trend
- `MACD_Line` [APPROVED] · Score: 79.7 · Category: Trend
- `MACD_Signal` [APPROVED] · Score: 79.6 · Category: Trend
- `Market_Structure` [PROMISING] · Score: 45.3 · Category: Structure
- `Price_vs_EMA20` [APPROVED] · Score: 68.3 · Category: Trend
- `Price_vs_EMA50` [APPROVED] · Score: 81.0 · Category: Trend
- `Price_vs_VWAP` [APPROVED] · Score: 78.1 · Category: Volume
- `RSI_14` [PROMISING] · Score: 53.0 · Category: Momentum
- `Regime_Bias` [PROMISING] · Score: 54.5 · Category: Composite
- `SR_Resistance` [PROMISING] · Score: 62.3 · Category: Structure
- `SR_Support` [PROMISING] · Score: 46.5 · Category: Structure
- `Signal_Desk_Score` [PROMISING] · Score: 46.6 · Category: Composite
- `Trend_Score` [PROMISING] · Score: 48.8 · Category: Composite

### Q2: Which features collapse?

**22 features collapse** (REJECT):

- `ATR_14` · Score: 28.9 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `BB_Position` · Score: 23.2 · Decay: MIXED · Reason: Score 23.2/100 — insufficient predictive power
- `BB_Width` · Score: 49.3 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `DI_Plus` · Score: 12.5 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Doji` · Score: 0.4 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Gap_Down` · Score: 23.0 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Gap_Up` · Score: 10.8 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `HH_HL_Pattern` · Score: 12.9 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Hammer` · Score: 25.0 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Liquidity_Sweep` · Score: 23.6 · Decay: MIXED · Reason: Score 23.6/100 — insufficient predictive power
- `Marubozu_Bull` · Score: 24.8 · Decay: SATURATION · Reason: Score 24.8/100 — insufficient predictive power
- `OBV` · Score: 15.6 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `OBV_Slope` · Score: 8.9 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `RSI_Divergence` · Score: 17.7 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Shooting_Star` · Score: 25.0 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `StochRSI_K` · Score: 7.8 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Stoch_D` · Score: 24.1 · Decay: MIXED · Reason: Score 24.1/100 — insufficient predictive power
- `Stoch_K` · Score: 23.4 · Decay: MIXED · Reason: Score 23.4/100 — insufficient predictive power
- `Supertrend` · Score: 4.0 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Supertrend_Dir` · Score: 24.5 · Decay: MIXED · Reason: Score 24.5/100 — insufficient predictive power
- `Vol_Ratio` · Score: 9.3 · Decay: SIGNAL_REVERSAL · Reason: Signal reversal — direction inverts at longer horizons
- `Vol_Surge` · Score: 23.9 · Decay: SATURATION · Reason: Score 23.9/100 — insufficient predictive power

### Q3: Which features remain robust across regimes?

**2 features demonstrate cross-regime robustness** (regime variance < 0.005):

- `BB_Upper` · Avg Corr: -0.2672 · Regime Var: 0.002703
- `Price_vs_VWAP` · Avg Corr: -0.2136 · Regime Var: 0.004791

### Q4: Which features qualify for V7.3 integration?

**11 features qualify for V7.3 Market Structure Engine:**

| Feature | Quality Score | Category | Time Stability | Decay Type |
|---|---|---|---|---|
| `ADX_14` | 65.5 | Strength | MODERATE | MIXED |
| `BB_Squeeze` | 65.1 | Volatility | MODERATE | MIXED |
| `BB_Upper` | 73.4 | Volatility | STABLE | SATURATION |
| `EMA_20` | 66.8 | Trend | STABLE | SATURATION |
| `EMA_21` | 66.6 | Trend | STABLE | SATURATION |
| `EMA_9` | 66.7 | Trend | STABLE | MIXED |
| `MACD_Line` | 79.7 | Trend | STABLE | MIXED |
| `MACD_Signal` | 79.6 | Trend | STABLE | IMPROVING |
| `Price_vs_EMA20` | 68.3 | Trend | MODERATE | MIXED |
| `Price_vs_EMA50` | 81.0 | Trend | STABLE | MIXED |
| `Price_vs_VWAP` | 78.1 | Volume | STABLE | MIXED |

---

## CATEGORY-LEVEL AUDIT RESULTS

| Category | Total | APPROVED | PROMISING | WATCHLIST | REJECT | Pass Rate |
|---|---|---|---|---|---|---|
| Candle | 6 | 0 | 0 | 2 | 4 | 0% |
| Composite | 5 | 0 | 3 | 2 | 0 | 60% |
| Momentum | 5 | 0 | 1 | 0 | 4 | 20% |
| Strength | 4 | 1 | 1 | 1 | 1 | 50% |
| Structure | 8 | 0 | 3 | 1 | 4 | 38% |
| Trend | 15 | 7 | 1 | 5 | 2 | 53% |
| Volatility | 6 | 2 | 0 | 1 | 3 | 33% |
| Volume | 6 | 1 | 0 | 1 | 4 | 17% |

---

## AUDIT CONCLUSION

| Metric | Value |
|---|---|
| Total Features Audited | 55 |
| V7.3 Eligible (APPROVED) | 11 |
| Pipeline (PROMISING) | 9 |
| Under Watch (WATCHLIST) | 13 |
| Eliminated (REJECT) | 22 |
| Average Quality Score | 39.4/100 |
| Cross-Regime Robust | 2 |

> **RULE: ONLY APPROVED features may enter the V7.3 Market Structure Engine.**

The audit has identified **11 APPROVED** features ready for V7.3 integration.
These features have demonstrated stable correlations across time periods,
acceptable regime variance, and no signal reversal. They form the approved
foundation of the V7.3 Market Structure Engine.

---

*WealthQuant V7.2.2 Alpha Stability Audit — generated by `alpha_stability_audit.py`*
