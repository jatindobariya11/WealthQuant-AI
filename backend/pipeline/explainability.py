"""
WealthQuant Explainability and Alpha Discovery Layer (V6).
Audits mathematical engines, performs ablation tests, regime attribution, and feature drift detection.
"""

import logging
import math
import os
from datetime import datetime

import numpy as np
import pandas as pd
from scipy import stats

from pipeline.config import FUSION_CONFIG
from pipeline.db import pipeline_db

logger = logging.getLogger("pipeline.explainability")


from core.shared_features import (
    compute_adx,
    compute_atr,
    compute_rsi,
    compute_volume_ratio,
)


class SignalExplainabilityManager:
    def __init__(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # Phase 7 Research Reports Paths
        self.debug_report_path = os.path.join(backend_dir, "debug_signal_report.csv")
        self.contribution_report_path = os.path.join(
            backend_dir, "feature_contribution_report.csv"
        )
        self.ablation_report_path = os.path.join(backend_dir, "ablation_report.csv")
        self.regime_report_path = os.path.join(
            backend_dir, "regime_performance_report.csv"
        )
        self.drift_report_path = os.path.join(backend_dir, "feature_drift_report.csv")

    def _load_csv(self, path: str, columns: list) -> pd.DataFrame:
        df = None
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                for col in columns:
                    if col not in df.columns:
                        df[col] = None
            except Exception as e:
                logger.error(f"Error reading CSV {path}: {e}")

        if df is None:
            df = pd.DataFrame(columns=columns)

        # Avoid dtype warnings when inserting boolean, integer or float values into empty columns
        for col in ["correct", "was_correct", "is_drifted"]:
            if col in df.columns:
                df[col] = df[col].astype(object)
        for col in ["actual_return", "baseline_mean", "recent_mean", "drift_score"]:
            if col in df.columns:
                df[col] = df[col].astype(object)
        return df

    def _save_csv(self, df: pd.DataFrame, path: str):
        try:
            df.to_csv(path, index=False)
        except Exception as e:
            logger.error(f"Error saving CSV to {path}: {e}")

    async def record_prediction(self, result, snapshot) -> bool:
        """
        Record current prediction details, calculate technical features, and persist.
        """
        try:
            symbol = result.symbol.upper()
            timestamp = result.timestamp
            spot_price = (
                float(snapshot.ohlcv["close"].values[-1])
                if snapshot and snapshot.ohlcv is not None
                else 1.0
            )

            # Extract internal states
            hawkes_score = result.hawkes.excitation_ratio if result.hawkes else None
            kalman_velocity = (
                result.kalman.estimated_velocity if result.kalman else None
            )
            particle_mean = result.particle.mean_price if result.particle else None
            regime_state = result.regime.current_regime if result.regime else None
            ensemble_prediction = (
                result.ensemble.predicted_return if result.ensemble else None
            )
            fusion_mean = result.fusion.fused_mean if result.fusion else None

            # Calculate Meta-learning prediction (adapted ensemble forecast q50) and weight
            meta_learning_prediction = ensemble_prediction
            if result.meta_learning and result.meta_learning.adapted_forecasts:
                fc = result.meta_learning.adapted_forecasts.get(5)
                if fc:
                    meta_learning_prediction = fc.q50

            regime_weights = FUSION_CONFIG.get("regime_weights", {}).get(
                regime_state or "TRANSITION", FUSION_CONFIG["initial_weights"]
            )
            meta_learning_weight = regime_weights.get("meta_learning", 0.20)

            # Probabilities and signals
            p_up = result.probabilities.p_up if result.probabilities else None
            p_down = result.probabilities.p_down if result.probabilities else None
            expected_return = (
                result.probabilities.expected_return if result.probabilities else None
            )
            kelly_fraction = (
                result.probabilities.kelly_fraction if result.probabilities else None
            )
            signal = result.probabilities.signal if result.probabilities else None
            signal_confidence = (
                result.probabilities.signal_confidence if result.probabilities else None
            )

            # Calculate technical indicator values for drift tracking
            rsi_val, adx_val, atr_val, vol_ratio_val = None, None, None, None
            if snapshot and hasattr(snapshot, "ohlcv") and snapshot.ohlcv is not None:
                df_ohlcv = snapshot.ohlcv
                if len(df_ohlcv) >= 14:
                    try:
                        rsi_val = float(compute_rsi(df_ohlcv["close"]).iloc[-1])
                        atr_val = float(
                            compute_atr(
                                df_ohlcv["high"], df_ohlcv["low"], df_ohlcv["close"]
                            ).iloc[-1]
                        )
                        adx_val = float(
                            compute_adx(
                                df_ohlcv["high"], df_ohlcv["low"], df_ohlcv["close"]
                            ).iloc[-1]
                        )
                        vol_ratio_val = float(
                            compute_volume_ratio(df_ohlcv["volume"]).iloc[-1]
                        )
                    except Exception as ind_err:
                        logger.warning(
                            f"Error calculating raw features for {symbol}: {ind_err}"
                        )

            pcr_val = 1.0
            if snapshot and hasattr(snapshot, "options") and snapshot.options:
                pcr_val = snapshot.options.get("pcr", 1.0)

            # Extract institutional positioning metrics if available
            inst_forecast = (
                result.institutional.forecast if result.institutional else None
            )
            inst_confidence = (
                result.institutional.confidence if result.institutional else None
            )
            pos_strength = (
                result.institutional.positioning_strength
                if result.institutional
                else None
            )
            bull_score = (
                result.institutional.bullish_score if result.institutional else None
            )
            bear_score = (
                result.institutional.bearish_score if result.institutional else None
            )
            neut_score = (
                result.institutional.neutral_score if result.institutional else None
            )
            pcr_val = result.institutional.pcr if result.institutional else pcr_val
            gamma_press = (
                result.institutional.gamma_pressure if result.institutional else None
            )
            dealer_press = (
                result.institutional.dealer_pressure if result.institutional else None
            )

            db_record = {
                "symbol": symbol,
                "timestamp": timestamp,
                "spot_price": spot_price,
                "hawkes_score": hawkes_score,
                "kalman_velocity": kalman_velocity,
                "particle_mean": particle_mean,
                "regime_state": regime_state,
                "ensemble_prediction": ensemble_prediction,
                "meta_learning_weight": meta_learning_weight,
                "fusion_mean": fusion_mean,
                "p_up": p_up,
                "p_down": p_down,
                "expected_return": expected_return,
                "kelly_fraction": kelly_fraction,
                "signal": signal,
                "signal_confidence": signal_confidence,
                "actual_return": None,
                "correct": None,
                "institutional_forecast": inst_forecast,
                "institutional_confidence": inst_confidence,
                "positioning_strength": pos_strength,
                "bullish_score": bull_score,
                "bearish_score": bear_score,
                "neutral_score": neut_score,
                "pcr_val": pcr_val,
                "gamma_pressure": gamma_press,
                "dealer_pressure": dealer_press,
            }

            csv_record = db_record.copy()
            csv_record["rsi"] = rsi_val
            csv_record["adx"] = adx_val
            csv_record["atr"] = atr_val
            csv_record["volume_ratio"] = vol_ratio_val
            csv_record["pcr"] = pcr_val
            csv_record["meta_learning_prediction"] = meta_learning_prediction

            # Sanitize floats to avoid PostgreSQL JSON NaN insertion errors
            for d in [db_record, csv_record]:
                for k, v in d.items():
                    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                        d[k] = None

            # 1. Save to database if connected
            db_success = False
            if pipeline_db.is_connected:
                db_success = await pipeline_db.insert_signal_explanation(db_record)

            # 2. Append/Update in local debug CSV (stores all fields including indicator features)
            cols = list(csv_record.keys())
            df = self._load_csv(self.debug_report_path, cols)

            ts_str = (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            )
            match_mask = (df["symbol"] == symbol) & (df["timestamp"] == ts_str)

            if match_mask.any():
                idx = df[match_mask].index[0]
                for col, val in csv_record.items():
                    if (
                        col not in ["actual_return", "correct"]
                        or df.at[idx, col] is None
                    ):
                        df.at[idx, col] = val
            else:
                row = csv_record.copy()
                row["timestamp"] = ts_str
                if df.empty:
                    df = pd.DataFrame([row], columns=cols)
                else:
                    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)

            self._save_csv(df, self.debug_report_path)
            logger.info(
                f"Recorded V6 explainability metrics for {symbol} at {timestamp} (DB: {db_success})"
            )
            return True

        except Exception as e:
            logger.error(f"Error in record_prediction: {e}", exc_info=True)
            return False

    async def update_and_analyze(
        self, symbol: str, timestamp, actual_return: float
    ) -> bool:
        """
        Update evaluation outcome and trigger contribution, ablation, regime, and drift analyses.
        """
        try:
            symbol = symbol.upper()
            ts_str = (
                timestamp.isoformat()
                if hasattr(timestamp, "isoformat")
                else str(timestamp)
            )

            # 1. Update in PostgreSQL
            db_success = False
            if pipeline_db.is_connected:
                db_success = await pipeline_db.update_signal_explanation_outcome(
                    symbol, timestamp, actual_return
                )

            # 2. Update in CSV
            # Execute only if DB update failed OR debug mode is explicitly enabled
            debug_mode = os.getenv("WEALTHQUANT_DEBUG_CSV") == "1"
            if (not db_success or debug_mode) and (
                os.path.exists(self.debug_report_path)
                and os.path.getsize(self.debug_report_path) > 0
            ):
                try:
                    df = pd.read_csv(self.debug_report_path)
                except Exception as csv_err:
                    logger.warning(
                        f"Failed to read CSV report {self.debug_report_path}: {csv_err}"
                    )
                    df = pd.DataFrame()
            else:
                df = pd.DataFrame()

            if df.empty or "symbol" not in df.columns:
                if not db_success:
                    return False
            else:
                match_mask = (df["symbol"] == symbol) & (df["timestamp"] == ts_str)
                if not match_mask.any():
                    logger.warning(
                        f"Could not find matching prediction row to evaluate for {symbol} at {ts_str} in CSV."
                    )
                    if not db_success:
                        return False
                else:
                    idx = df[match_mask].index[0]
                    sig = df.at[idx, "signal"]

                    correct = False
                    if sig in ["BUY", "STRONG_BUY"]:
                        correct = actual_return > 0.005
                    elif sig in ["SELL", "STRONG_SELL"]:
                        correct = actual_return < -0.005
                    elif sig == "NEUTRAL":
                        correct = abs(actual_return) <= 0.005

                    df["correct"] = df["correct"].astype(object)
                    df["actual_return"] = df["actual_return"].astype(object)
                    df.at[idx, "actual_return"] = actual_return
                    df.at[idx, "correct"] = correct
                    self._save_csv(df, self.debug_report_path)

            # 3. Recalculate research layers asynchronously
            import asyncio

            asyncio.create_task(self._run_analysis_pipeline(symbol))
            return True

        except Exception as e:
            logger.error(f"Error in update_and_analyze: {e}", exc_info=True)
            return False

    async def _run_analysis_pipeline(self, symbol: str):
        """
        Runs the full Phase 2-6 evaluation algorithms and exports reports to DB and CSV.
        """
        try:
            records = []
            if pipeline_db.is_connected:
                records = await pipeline_db.get_evaluated_signal_explanations(
                    symbol, limit=1000
                )

            if not records:
                df = pd.read_csv(self.debug_report_path)
                df_eval = df[(df["symbol"] == symbol) & (df["actual_return"].notna())]
                records = df_eval.to_dict(orient="records")

            if not records:
                logger.warning(
                    f"No evaluated predictions found to analyze for {symbol}."
                )
                return

            # Extract price and actual returns
            spots = np.array([r["spot_price"] for r in records], dtype=float)
            actuals = np.array([r["actual_return"] for r in records], dtype=float)
            n_samples = len(actuals)

            # Extract 6 stage predictions
            stage_preds = {
                "Kalman": np.array(
                    [
                        (r["kalman_velocity"] * 5) / r["spot_price"]
                        if r["kalman_velocity"] is not None
                        else 0.0
                        for r in records
                    ]
                ),
                "Particle": np.array(
                    [
                        (r["particle_mean"] - r["spot_price"]) / r["spot_price"]
                        if r["particle_mean"] is not None
                        else 0.0
                        for r in records
                    ]
                ),
                "Ensemble": np.array(
                    [
                        r["ensemble_prediction"]
                        if r["ensemble_prediction"] is not None
                        else 0.0
                        for r in records
                    ]
                ),
                "Meta Learning": np.array(
                    [
                        r.get("meta_learning_prediction", r["ensemble_prediction"])
                        if r.get("meta_learning_prediction") is not None
                        else 0.0
                        for r in records
                    ]
                ),
                "Institutional": np.array(
                    [
                        r.get("institutional_forecast")
                        if r.get("institutional_forecast") is not None
                        else 0.0
                        for r in records
                    ]
                ),
                "Fusion": np.array(
                    [
                        r["fusion_mean"] if r["fusion_mean"] is not None else 0.0
                        for r in records
                    ]
                ),
            }

            # ─── PHASE 2: CORE METRICS ───
            # Calculate standard indicators for mathematical stages
            core_results = []
            for stage, preds in stage_preds.items():
                dir_acc = np.mean(
                    ((preds > 0) & (actuals > 0))
                    | ((preds < 0) & (actuals < 0))
                    | ((preds == 0) & (actuals == 0))
                )
                mae = np.mean(np.abs(preds - actuals))
                rmse = np.sqrt(np.mean((preds - actuals) ** 2))

                corr = 0.0
                if n_samples >= 2 and np.std(preds) > 0 and np.std(actuals) > 0:
                    corr = float(np.corrcoef(preds, actuals)[0, 1])
                    if np.isnan(corr):
                        corr = 0.0

                stability = (
                    1.0 / (1.0 + np.std(np.diff(preds))) if len(preds) > 1 else 1.0
                )
                core_results.append(
                    {
                        "stage": stage,
                        "accuracy": dir_acc,
                        "mae": mae,
                        "rmse": rmse,
                        "correlation": corr,
                        "stability": stability,
                    }
                )

            # ─── PHASE 3: STAGE CONTRIBUTIONS (Sharpe and Drawdown) ───
            stage_contribs = []
            for stage, preds in stage_preds.items():
                # Simulate strategy returns
                strat_rets = np.sign(preds) * actuals
                mean_ret = np.mean(strat_rets)
                std_ret = np.std(strat_rets)

                # Sharpe
                sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0

                # Drawdown
                cum_rets = np.cumsum(strat_rets)
                running_max = np.maximum.accumulate(cum_rets)
                drawdowns = running_max - cum_rets
                max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

                # Get core metrics for this stage
                core = next(c for c in core_results if c["stage"] == stage)

                status = "NEUTRAL"
                if core["correlation"] > 0.05:
                    status = "HELPING"
                elif core["correlation"] < -0.05:
                    status = "HURTING"

                stage_contribs.append(
                    {
                        "symbol": symbol,
                        "stage": stage,
                        "accuracy": core["accuracy"],
                        "correlation": core["correlation"],
                        "mae": core["mae"],
                        "sharpe_contribution": sharpe,
                        "drawdown_contribution": max_dd,
                        "status": status,
                    }
                )

            # Save stage contributions
            if pipeline_db.is_connected:
                await pipeline_db.insert_stage_contributions(stage_contribs)

            contrib_df = pd.DataFrame(stage_contribs)
            contrib_df["updated_at"] = datetime.now().isoformat()
            self._save_csv(contrib_df, self.contribution_report_path)

            # ─── PHASE 4: ABLATION TESTING ───
            # Re-fuse return prediction excluding individual stages
            # Map weights based on regime state in record
            ablation_simulations = {
                "Full System": np.array(
                    [
                        r["fusion_mean"] if r["fusion_mean"] is not None else 0.0
                        for r in records
                    ]
                ),
                "Without Kalman": [],
                "Without Particle": [],
                "Without Ensemble": [],
                "Without Fusion": [],
                "Without Meta Learning": [],
                "Without Institutional": [],
            }

            for idx, r in enumerate(records):
                regime = r["regime_state"] or "TRANSITION"
                weights_dict = FUSION_CONFIG.get("regime_weights", {}).get(
                    regime, FUSION_CONFIG["initial_weights"]
                )

                w_hawkes = weights_dict.get("hawkes", 0.10)
                w_kalman = weights_dict.get("kalman", 0.15)
                w_particle = weights_dict.get("particle", 0.15)
                w_ensemble = weights_dict.get("ensemble", 0.60)  # combined weight
                w_inst = weights_dict.get("institutional", 0.0)

                # Fetch returns
                h_ret = 0.0
                k_ret = stage_preds["Kalman"][idx]
                p_ret = stage_preds["Particle"][idx]
                e_ret = stage_preds["Ensemble"][idx]
                m_ret = stage_preds["Meta Learning"][idx]
                i_ret = stage_preds["Institutional"][idx]

                # Without Kalman (set w_kalman = 0)
                pred_no_kalman = (
                    w_particle * p_ret + w_ensemble * m_ret + w_inst * i_ret
                ) / (w_hawkes + w_particle + w_ensemble + w_inst)
                ablation_simulations["Without Kalman"].append(pred_no_kalman)

                # Without Particle (set w_particle = 0)
                pred_no_particle = (
                    w_kalman * k_ret + w_ensemble * m_ret + w_inst * i_ret
                ) / (w_hawkes + w_kalman + w_ensemble + w_inst)
                ablation_simulations["Without Particle"].append(pred_no_particle)

                # Without Ensemble (set w_ensemble = 0)
                pred_no_ensemble = (
                    w_kalman * k_ret + w_particle * p_ret + w_inst * i_ret
                ) / (w_hawkes + w_kalman + w_particle + w_inst)
                ablation_simulations["Without Ensemble"].append(pred_no_ensemble)

                # Without Fusion (outputs Meta Learning adapted q50 directly)
                ablation_simulations["Without Fusion"].append(m_ret)

                # Without Meta Learning (uses unadapted Ensemble predicted return)
                pred_no_meta = (
                    w_kalman * k_ret
                    + w_particle * p_ret
                    + w_ensemble * e_ret
                    + w_inst * i_ret
                ) / (w_hawkes + w_kalman + w_particle + w_ensemble + w_inst)
                ablation_simulations["Without Meta Learning"].append(pred_no_meta)

                # Without Institutional (set w_inst = 0)
                pred_no_inst = (
                    w_kalman * k_ret + w_particle * p_ret + w_ensemble * m_ret
                ) / (w_hawkes + w_kalman + w_particle + w_ensemble)
                ablation_simulations["Without Institutional"].append(pred_no_inst)

            # Convert to numpy arrays
            for config in ablation_simulations:
                ablation_simulations[config] = np.array(ablation_simulations[config])

            # Calculate performance metrics for each ablated configuration
            full_system_rets = np.sign(ablation_simulations["Full System"]) * actuals
            ablation_results = []

            for config, preds in ablation_simulations.items():
                strat_rets = np.sign(preds) * actuals
                mean_ret = np.mean(strat_rets)
                std_ret = np.std(strat_rets)

                sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0

                downside_rets = strat_rets[strat_rets < 0]
                downside_std = np.std(downside_rets) if len(downside_rets) > 0 else 0.0
                sortino = (
                    (mean_ret / downside_std) * np.sqrt(252)
                    if downside_std > 0
                    else 0.0
                )

                cum_rets = np.cumsum(strat_rets)
                running_max = np.maximum.accumulate(cum_rets)
                drawdowns = running_max - cum_rets
                max_dd = np.max(drawdowns) if len(drawdowns) > 0 else 0.0

                win_rate = np.mean(strat_rets > 0)

                pos_sum = np.sum(strat_rets[strat_rets > 0])
                neg_sum = abs(np.sum(strat_rets[strat_rets < 0]))
                profit_factor = (
                    pos_sum / neg_sum if neg_sum > 0 else (1.0 if pos_sum > 0 else 0.0)
                )

                # p-value relative to Full System (t-test on strategy returns)
                p_val = 1.0
                if config != "Full System" and n_samples >= 2:
                    try:
                        res = stats.ttest_rel(full_system_rets, strat_rets)
                        p_val = float(res.pvalue) if not np.isnan(res.pvalue) else 1.0
                    except Exception:
                        p_val = 1.0

                ablation_results.append(
                    {
                        "symbol": symbol,
                        "configuration": config,
                        "sharpe": sharpe,
                        "sortino": sortino,
                        "max_drawdown": max_dd,
                        "win_rate": win_rate,
                        "profit_factor": profit_factor,
                        "p_value": p_val,
                    }
                )

            if pipeline_db.is_connected:
                await pipeline_db.insert_ablation_results(ablation_results)

            ablation_df = pd.DataFrame(ablation_results)
            ablation_df["updated_at"] = datetime.now().isoformat()
            self._save_csv(ablation_df, self.ablation_report_path)

            # ─── PHASE 5: REGIME ATTRIBUTION ───
            # Regimes: Bull (TRENDING_BULL), Bear (TRENDING_BEAR), Sideways (others)
            regime_mapping = {
                "Bull": ["TRENDING_BULL"],
                "Bear": ["TRENDING_BEAR"],
                "Sideways": [
                    "MEAN_REVERTING",
                    "LOW_VOLATILITY",
                    "HIGH_VOLATILITY",
                    "TRANSITION",
                ],
            }

            regime_performance = []
            for regime_label, states in regime_mapping.items():
                # Filter records matching regime states
                regime_indices = [
                    i for i, r in enumerate(records) if r["regime_state"] in states
                ]
                if not regime_indices:
                    continue

                regime_actuals = actuals[regime_indices]
                regime_n = len(regime_actuals)

                for stage, preds in stage_preds.items():
                    regime_preds = preds[regime_indices]

                    dir_acc = np.mean(
                        ((regime_preds > 0) & (regime_actuals > 0))
                        | ((regime_preds < 0) & (regime_actuals < 0))
                        | ((regime_preds == 0) & (regime_actuals == 0))
                    )
                    mae = np.mean(np.abs(regime_preds - regime_actuals))

                    corr = 0.0
                    if (
                        regime_n >= 2
                        and np.std(regime_preds) > 0
                        and np.std(regime_actuals) > 0
                    ):
                        corr = float(np.corrcoef(regime_preds, regime_actuals)[0, 1])
                        if np.isnan(corr):
                            corr = 0.0

                    regime_performance.append(
                        {
                            "symbol": symbol,
                            "regime": regime_label,
                            "stage": stage,
                            "accuracy": dir_acc,
                            "correlation": corr,
                            "mae": mae,
                        }
                    )

            if pipeline_db.is_connected and regime_performance:
                await pipeline_db.insert_regime_performance(regime_performance)

            if regime_performance:
                regime_df = pd.DataFrame(regime_performance)
                regime_df["updated_at"] = datetime.now().isoformat()
                self._save_csv(regime_df, self.regime_report_path)

            # ─── PHASE 6: FEATURE DRIFT DETECTION ───
            # Load indicator history from local debug report (last 100 rows baseline, last 20 recent)
            df_full = pd.read_csv(self.debug_report_path)
            df_symbol = df_full[df_full["symbol"] == symbol]

            features_to_monitor = ["rsi", "adx", "atr", "volume_ratio", "pcr"]
            drift_results = []

            for col in features_to_monitor:
                feature_series = df_symbol[col].dropna()
                n_total = len(feature_series)

                if n_total < 10:
                    continue

                # Baseline is historical (up to last 100)
                baseline = feature_series.tail(100)
                # Recent window (last 20)
                recent = feature_series.tail(20)

                b_mean = float(baseline.mean())
                b_std = float(baseline.std())
                r_mean = float(recent.mean())

                drift_score = 0.0
                if b_std > 1e-6:
                    drift_score = abs(r_mean - b_mean) / b_std

                is_drifted = bool(drift_score > 2.0 and len(baseline) >= 10)

                # Map standard feature name for report
                name_map = {
                    "rsi": "RSI",
                    "adx": "ADX",
                    "atr": "ATR",
                    "volume_ratio": "Volume Ratio",
                    "pcr": "PCR",
                }

                drift_results.append(
                    {
                        "symbol": symbol,
                        "feature_name": name_map.get(col, col),
                        "baseline_mean": b_mean,
                        "recent_mean": r_mean,
                        "drift_score": drift_score,
                        "is_drifted": is_drifted,
                    }
                )

            if pipeline_db.is_connected and drift_results:
                await pipeline_db.insert_feature_drift(drift_results)

            if drift_results:
                drift_df = pd.DataFrame(drift_results)
                drift_df["updated_at"] = datetime.now().isoformat()
                self._save_csv(drift_df, self.drift_report_path)

            # ─── PRINT LOG SUCCESS SUMMARY ───
            logger.info(
                f"WealthQuant V6 research pipeline successfully evaluated for {symbol}."
            )

        except Exception as ex:
            logger.error(f"Error executing analysis pipeline: {ex}", exc_info=True)
