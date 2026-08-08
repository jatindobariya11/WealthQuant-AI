# 🔬 WealthQuant V7.2 — Options Research Report

> **Generated:** 2026-06-20 18:22:22 IST  
> **Database Source:** Real Options Warehouse (PG Fallback Mode)  
> **Analyzed Sample Size:** 8 intervals

---

## 🏆 Top 10 Features (1-Day Horizon)

Ranked by Composite Score (combining absolute correlation, statistical significance, stability, and regime consistency).

| Rank | Feature | Correlation | p-value | Info Ratio | Stability | Composite Score |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 1 | `fii_dii_ratio` | 0.4746 | 0.2348 | 35.06 | 1.0000 | 0.1816 |
| 2 | `combined_flow` | 0.4315 | 0.2857 | 34.87 | 1.0000 | 0.1541 |
| 3 | `dii_net` | 0.3091 | 0.4562 | 31.49 | 1.0000 | 0.0841 |
| 4 | `fii_net` | 0.2729 | 0.5132 | 25.67 | 1.0000 | 0.0664 |
| 5 | `atm_iv` | 0.1262 | 0.7660 | 11.54 | 1.0000 | 0.0148 |
| 6 | `strike_migration` | -0.1221 | 0.7734 | 17.37 | 1.0000 | 0.0138 |
| 7 | `pcr_momentum` | 0.1208 | 0.7756 | 17.21 | 1.0000 | 0.0136 |
| 8 | `oi_velocity` | 0.1208 | 0.7757 | 17.20 | 1.0000 | 0.0135 |
| 9 | `oi_momentum` | -0.1004 | 0.8130 | 9.75 | 1.0000 | 0.0094 |
| 10 | `put_wall_dist` | -0.0722 | 0.8652 | 9.57 | 1.0000 | 0.0049 |

---

## 📉 Worst 10 Features (1-Day Horizon)

| Rank | Feature | Correlation | p-value | Info Ratio | Stability | Composite Score |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|
| 9 | `oi_momentum` | -0.1004 | 0.8130 | 9.75 | 1.0000 | 0.0094 |
| 10 | `put_wall_dist` | -0.0722 | 0.8652 | 9.57 | 1.0000 | 0.0049 |
| 11 | `call_wall_dist` | 0.0613 | 0.8854 | 8.11 | 1.0000 | 0.0035 |
| 12 | `pcr_oi` | 0.0213 | 0.9601 | 1.96 | 1.0000 | 0.0004 |
| 13 | `pcr_vol` | 0.0213 | 0.9601 | 1.96 | 1.0000 | 0.0004 |
| 14 | `volume_oi_ratio` | 0.0133 | 0.9751 | 1.12 | 1.0000 | 0.0002 |
| 15 | `call_wall_oi_chg` | 0.0000 | 1.0000 | 0.00 | 1.0000 | 0.0000 |
| 16 | `max_pain_migration` | 0.0000 | 1.0000 | 0.00 | 1.0000 | 0.0000 |
| 17 | `put_wall_oi_chg` | 0.0000 | 1.0000 | 0.00 | 1.0000 | 0.0000 |
| 18 | `max_pain_dist` | 0.0000 | 1.0000 | 0.00 | 1.0000 | 0.0000 |

---

## 📊 Feature Stability & Regime Consistency

Feature performance (stability and regime consistency std dev) across folds and market regimes (lower is more stable/consistent).

| Feature | Correlation | Fold Stability (Std) | Regime Consistency (Std) | Composite Score |
|:---|:---:|:---:|:---:|:---:|
| `fii_dii_ratio` | 0.4746 | 1.0000 | 1.0000 | 0.1816 |
| `combined_flow` | 0.4315 | 1.0000 | 1.0000 | 0.1541 |
| `dii_net` | 0.3091 | 1.0000 | 1.0000 | 0.0841 |
| `fii_net` | 0.2729 | 1.0000 | 1.0000 | 0.0664 |
| `atm_iv` | 0.1262 | 1.0000 | 1.0000 | 0.0148 |
| `strike_migration` | -0.1221 | 1.0000 | 1.0000 | 0.0138 |
| `pcr_momentum` | 0.1208 | 1.0000 | 1.0000 | 0.0136 |
| `oi_velocity` | 0.1208 | 1.0000 | 1.0000 | 0.0135 |
| `oi_momentum` | -0.1004 | 1.0000 | 1.0000 | 0.0094 |
| `put_wall_dist` | -0.0722 | 1.0000 | 1.0000 | 0.0049 |
| `call_wall_dist` | 0.0613 | 1.0000 | 1.0000 | 0.0035 |
| `pcr_oi` | 0.0213 | 1.0000 | 1.0000 | 0.0004 |
| `pcr_vol` | 0.0213 | 1.0000 | 1.0000 | 0.0004 |
| `volume_oi_ratio` | 0.0133 | 1.0000 | 1.0000 | 0.0002 |
| `call_wall_oi_chg` | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| `max_pain_migration` | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| `put_wall_oi_chg` | 0.0000 | 1.0000 | 1.0000 | 0.0000 |
| `max_pain_dist` | 0.0000 | 1.0000 | 1.0000 | 0.0000 |

---

## 🌍 Regime Performance Breakdown (Correlation)

Pearson correlation coefficients across different market regimes (Bull, Bear, Sideways, High Volatility, Low Volatility).

| Feature | Horizon | Bull | Bear | Sideways | High Vol | Low Vol |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| `fii_dii_ratio` | 1d | +0.4828 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `combined_flow` | 1d | +0.5181 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `dii_net` | 1d | +0.5036 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `fii_net` | 1d | -0.0100 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `atm_iv` | 1d | -0.1494 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `strike_migration` | 1d | +0.1228 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `pcr_momentum` | 1d | -0.1246 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `oi_velocity` | 1d | -0.1247 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `oi_momentum` | 1d | +0.0674 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `put_wall_dist` | 1d | -0.2894 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `call_wall_dist` | 1d | +0.2727 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `pcr_oi` | 1d | +0.4385 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `pcr_vol` | 1d | +0.4385 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `volume_oi_ratio` | 1d | +0.4907 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `call_wall_oi_chg` | 1d | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `max_pain_migration` | 1d | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `put_wall_oi_chg` | 1d | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |
| `max_pain_dist` | 1d | +0.0000 | +0.0000 | +0.0000 | +0.0000 | +0.0000 |

---

## 💡 Alpha Candidates

Features displaying statistically significant predictive power (p-value < 0.05).

> ⚠️ **No alpha candidates detected.** Accumulating more real options data is required to establish statistical significance.


*Report complete. All metrics calculated from real, non-synthetic option chains.*