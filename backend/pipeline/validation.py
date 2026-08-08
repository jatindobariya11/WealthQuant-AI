"""
WealthQuant Validation & Monte Carlo Framework.
Implements Walk Forward Validation (rolling splits, retraining, DDL insertion)
and Monte Carlo statistical edge testing.
"""

import json
import logging
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    matthews_corrcoef,
    precision_recall_fscore_support,
    roc_auc_score,
)

from pipeline.backtest_engine import BacktestEngine
from pipeline.config import ENSEMBLE_CONFIG, RESEARCH_CONFIG
from pipeline.db import pipeline_db
from pipeline.stage6_ensemble import Stage6Ensemble

logger = logging.getLogger("pipeline.validation")


def compute_ece(y_true, y_prob, n_bins=10):
    """Computes Expected Calibration Error."""
    if not len(y_true):
        return 0.0
    prob_true, prob_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="uniform"
    )

    # Calculate bin weights
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    binned = np.digitize(y_prob, bins) - 1

    bin_weights = np.zeros(n_bins)
    for i in range(n_bins):
        bin_weights[i] = len(y_prob[binned == i]) / len(y_prob)

    # ECE is weighted average of absolute difference between predicted and empirical prob
    ece = 0.0
    for i in range(len(prob_true)):
        ece += np.abs(prob_true[i] - prob_pred[i]) * bin_weights[i]
    return float(ece)


class WalkForwardValidator:
    def __init__(
        self,
        initial_capital: float = 10000000.0,
        order_type: str = "INTRADAY",
        kelly_cap: float = 0.10,
    ):

        self.initial_capital = initial_capital
        self.order_type = order_type
        self.kelly_cap = kelly_cap
        self.ensemble_stage = Stage6Ensemble()

    def get_ensemble_feature_importances(self, symbol: str, horizon: int = 5) -> dict:
        """
        Loads the saved ensemble model and extracts feature importances.
        """
        model_dir = ENSEMBLE_CONFIG.get("model_dir", "pipeline/models")
        model_path = os.path.join(
            model_dir, f"{symbol.upper()}_horizon_{horizon}.joblib"
        )

        if not os.path.exists(model_path):
            return {}

        try:
            h_models = joblib.load(model_path)
            xgb_model = h_models.get("xgb_q_0.5")

            if xgb_model and hasattr(xgb_model, "feature_importances_"):
                # Reconstruct sorted feature names list matching Stage 6 Ensemble
                # Let's build a dummy dataframe to extract the keys
                dummy_keys = [
                    "return_1d",
                    "return_3d",
                    "return_5d",
                    "return_10d",
                    "return_20d",
                    "momentum",
                    "volatility_kalman",
                    "volatility_particle",
                    "bb_width",
                    "atr_pct",
                    "volume_ratio",
                    "rsi",
                    "adx",
                    "hawkes_intensity_ratio",
                    "hawkes_branching_ratio",
                    "hawkes_is_cascade",
                    "kalman_velocity",
                    "kalman_acceleration",
                    "kalman_innovation_z",
                    "particle_skewness",
                    "particle_kurtosis",
                    "particle_bimodality",
                    "particle_tail_left",
                    "particle_tail_right",
                    "regime_transition_prob",
                    "options_pcr",
                    "options_oi_score",
                    "options_atm_iv",
                    "calendar_day_of_week",
                    "calendar_month",
                    "sector_avg_return",
                ]
                for r_name in [
                    "TRENDING_BULL",
                    "TRENDING_BEAR",
                    "MEAN_REVERTING",
                    "HIGH_VOLATILITY",
                    "LOW_VOLATILITY",
                    "TRANSITION",
                ]:
                    dummy_keys.append(f"regime_{r_name}")

                feature_names = sorted(dummy_keys)
                importances = xgb_model.feature_importances_

                feat_imp = {}
                for name, imp in zip(feature_names, importances):
                    feat_imp[name] = float(imp)

                # Sort descending
                return dict(sorted(feat_imp.items(), key=lambda x: -x[1]))
        except Exception as e:
            logger.warning(f"Failed to load feature importances: {e}")

        return {}

    async def run_walk_forward(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str = "15m",
        train_bars: int = 500,
        test_bars: int = 100,
        n_folds: int = 4,
    ) -> dict:
        """
        Runs walk forward validation: rolling train/test splits, fitting models on training,
        evaluating out-of-sample on test blocks, and persisting results.
        """
        df = df.sort_index()
        n_bars = len(df)

        required_bars = train_bars + (test_bars * n_folds)
        if n_bars < required_bars:
            raise ValueError(
                f"Insufficient history ({n_bars} bars) for {n_folds} folds of size {test_bars} and training {train_bars}."
            )

        logger.info(
            f"Running Walk Forward Validation on {symbol} ({timeframe}): {n_folds} folds."
        )

        target_mode = RESEARCH_CONFIG.get("target_mode", "STATIC")
        base_threshold = RESEARCH_CONFIG.get("classification_threshold", 0.005)
        rolling_window = RESEARCH_CONFIG.get("rolling_window", 20)
        std_multiplier = RESEARCH_CONFIG.get("std_multiplier", 1.5)
        pred_horizon = RESEARCH_CONFIG.get("prediction_horizon", 5)

        if target_mode == "VOLATILITY_ADAPTIVE":
            log_returns = np.log(df["close"] / df["close"].shift(1)).ffill().fillna(0.0)
            rolling_std = log_returns.rolling(rolling_window).std().ffill().fillna(0.01)
        else:
            rolling_std = pd.Series(0.0, index=df.index)

        # Initialize registry experiment entry
        experiment_record = {
            "name": f"WFW_{symbol}_{timeframe}",
            "description": f"Walk Forward Validation with {n_folds} folds, train={train_bars}, test={test_bars}",
            "strategy_config": {
                "train_bars": train_bars,
                "test_bars": test_bars,
                "n_folds": n_folds,
                "kelly_cap": self.kelly_cap,
                "target_mode": target_mode,
                "std_multiplier": std_multiplier,
                "rolling_window": rolling_window,
                "prediction_horizon": pred_horizon,
            },
            "metrics": {},
            "parameters": {"symbols": [symbol.upper()], "timeframe": timeframe},
        }

        # Save experiment to database if connected
        experiment_id = None
        if pipeline_db.is_connected:
            experiment_id = await pipeline_db.insert_experiment(experiment_record)
            logger.info(f"Registered Walk Forward Experiment with ID: {experiment_id}")

        fold_results = []
        all_y_true = []
        all_y_pred = []
        all_y_prob = []
        all_regimes = []
        all_realized_returns = []
        all_equity_values = []
        all_institutional_history = []

        # Starting capital for each out-of-sample fold
        cash_balance = self.initial_capital

        for fold in range(n_folds):
            # Define fold boundaries
            train_start_idx = fold * test_bars
            train_end_idx = train_start_idx + train_bars
            test_start_idx = train_end_idx
            test_end_idx = test_start_idx + test_bars

            train_df = df.iloc[train_start_idx:train_end_idx]
            test_df = df.iloc[test_start_idx - 20 : test_end_idx]

            logger.info(
                f"Fold {fold + 1}/{n_folds}: Train [{train_df.index[0]} to {train_df.index[-1]}], Test [{test_df.index[0]} to {test_df.index[-1]}]"
            )

            # Step 1: Retrain model on training block
            try:
                self.ensemble_stage.train(train_df, symbol)
            except Exception as train_err:
                logger.error(f"Training failed on fold {fold}: {train_err}")
                continue

            # Step 2: Backtest out-of-sample on testing block
            backtester = BacktestEngine(
                initial_capital=cash_balance,
                order_type=self.order_type,
                kelly_cap=self.kelly_cap,
            )
            # Link stages so they use the newly trained model in the folder
            backtester.stage6 = self.ensemble_stage

            backtest_res = await backtester.run_backtest(
                test_df, symbol, timeframe=timeframe, warmup_bars=20
            )

            # Carry over ending cash balance to simulate contiguous portfolio running
            cash_balance = backtest_res["equity_curve"]["values"][-1]
            all_equity_values.extend(backtest_res["equity_curve"]["values"])
            if "institutional_history" in backtest_res:
                all_institutional_history.extend(backtest_res["institutional_history"])

            # Step 3: Evaluate predictions accuracy metrics
            fold_y_true = []
            fold_y_pred = []
            fold_y_prob = []
            fold_regimes = []

            signals = backtest_res["results"]["signals"]
            # Skip warmup period in evaluation
            for item in signals:
                sig = item["signal"]
                # Map signal to classes: 1 (BUY), -1 (SELL), 0 (NEUTRAL)
                p_cls = (
                    1
                    if sig in ("BUY", "STRONG_BUY")
                    else (-1 if sig in ("SELL", "STRONG_SELL") else 0)
                )

                # Retrieve matching price pred_horizon bars ahead
                t_str = item["timestamp"]
                t_dt = pd.to_datetime(t_str)
                idx = test_df.index.get_loc(t_dt)
                df_idx = df.index.get_loc(t_dt)

                if idx + pred_horizon < len(test_df):
                    p_start = test_df["close"].iloc[idx]
                    p_end = test_df["close"].iloc[idx + pred_horizon]
                    ret = (p_end - p_start) / p_start

                    if target_mode == "VOLATILITY_ADAPTIVE":
                        vol = rolling_std.iloc[df_idx]
                        threshold = max(0.001, vol * std_multiplier)
                    else:
                        threshold = base_threshold

                    t_cls = 1 if ret > threshold else (-1 if ret < -threshold else 0)
                    fold_y_true.append(t_cls)
                    fold_y_pred.append(p_cls)

                    if "probabilities" in item and item["probabilities"]:
                        probs = item["probabilities"]
                        fold_y_prob.append(
                            [probs["p_down"], probs["p_sideways"], probs["p_up"]]
                        )
                    else:
                        fold_y_prob.append([0.33, 0.34, 0.33])

                    if "regime" in item:
                        fold_regimes.append(item["regime"])
                    else:
                        fold_regimes.append("UNKNOWN")

            # Calculate classification metrics
            acc = 0.0
            prec = 0.0
            rec = 0.0
            f1 = 0.0
            advanced_metrics = {}

            if fold_y_true:
                acc = float(accuracy_score(fold_y_true, fold_y_pred))
                p_stat, r_stat, f_stat, _ = precision_recall_fscore_support(
                    fold_y_true, fold_y_pred, average="macro", zero_division=0
                )
                prec = float(p_stat)
                rec = float(r_stat)
                f1 = float(f_stat)

                # Advanced Metrics
                advanced_metrics["mcc"] = float(
                    matthews_corrcoef(fold_y_true, fold_y_pred)
                )
                advanced_metrics["balanced_accuracy"] = float(
                    balanced_accuracy_score(fold_y_true, fold_y_pred)
                )
                advanced_metrics["confusion_matrix"] = confusion_matrix(
                    fold_y_true, fold_y_pred
                ).tolist()

                try:
                    # multiclass prob array
                    y_prob_arr = np.array(fold_y_prob)
                    # Convert true labels to 0, 1, 2 indices (-1 -> 0, 0 -> 1, 1 -> 2)
                    y_true_idx = np.array(fold_y_true) + 1

                    # One-hot true array
                    y_true_oh = np.zeros((len(y_true_idx), 3))
                    y_true_oh[np.arange(len(y_true_idx)), y_true_idx] = 1.0

                    advanced_metrics["roc_auc"] = float(
                        roc_auc_score(y_true_idx, y_prob_arr, multi_class="ovr")
                    )
                    advanced_metrics["pr_auc"] = (
                        0.0  # Average precision for multiclass needs custom or looping over classes
                    )

                    # Brier score (multi-class generalization)
                    brier = float(
                        np.mean(np.sum((y_true_oh - y_prob_arr) ** 2, axis=1))
                    )
                    advanced_metrics["brier_score"] = brier

                    # Expected Calibration Error (approximation using Buy class)
                    y_true_buy = (np.array(fold_y_true) == 1).astype(int)
                    y_prob_buy = y_prob_arr[:, 2]
                    advanced_metrics["ece_buy"] = compute_ece(y_true_buy, y_prob_buy)
                except Exception as e:
                    logger.warning(f"Could not compute advanced metrics: {e}")

                all_y_true.extend(fold_y_true)
                all_y_pred.extend(fold_y_pred)
                all_y_prob.extend(fold_y_prob)
                all_regimes.extend(fold_regimes)

            # Load feature importances
            feature_imp = self.get_ensemble_feature_importances(symbol, horizon=5)

            # Calculate label statistics
            label_stats = {
                "buys": fold_y_true.count(1),
                "sells": fold_y_true.count(-1),
                "neutrals": fold_y_true.count(0),
            }
            total_samples = len(fold_y_true) if fold_y_true else 1
            class_balance = {
                "buy_pct": label_stats["buys"] / total_samples,
                "sell_pct": label_stats["sells"] / total_samples,
                "neutral_pct": label_stats["neutrals"] / total_samples,
            }

            # Log fold result to PostgreSQL
            fold_record = {
                "experiment_id": experiment_id,
                "fold_index": fold + 1,
                "train_start": train_df.index[0].to_pydatetime()
                if hasattr(train_df.index[0], "to_pydatetime")
                else train_df.index[0],
                "train_end": train_df.index[-1].to_pydatetime()
                if hasattr(train_df.index[-1], "to_pydatetime")
                else train_df.index[-1],
                "test_start": test_df.index[0].to_pydatetime()
                if hasattr(test_df.index[0], "to_pydatetime")
                else test_df.index[0],
                "test_end": test_df.index[-1].to_pydatetime()
                if hasattr(test_df.index[-1], "to_pydatetime")
                else test_df.index[-1],
                "accuracy": acc,
                "precision_val": prec,
                "recall_val": rec,
                "f1_score": f1,
                "sharpe_ratio": backtest_res["sharpe_ratio"],
                "max_drawdown": backtest_res["max_drawdown"],
                "feature_importances": feature_imp,
                "metadata": {
                    "label_stats": label_stats,
                    "class_balance": class_balance,
                    "target_mode": target_mode,
                    "threshold_applied": threshold
                    if "threshold" in locals()
                    else base_threshold,
                    "advanced_metrics": advanced_metrics,
                    "regimes_present": list(set(fold_regimes)),
                },
            }

            if pipeline_db.is_connected and experiment_id:
                await pipeline_db.insert_walk_forward_result(fold_record)

            fold_results.append(fold_record)

            # Store all trades returns
            trades = backtest_res["results"]["trades"]
            all_realized_returns.extend([t["realized_pnl"] for t in trades])

        # ─── Aggregated Walk Forward Statistics ───
        overall_accuracy = (
            float(accuracy_score(all_y_true, all_y_pred)) if all_y_true else 0.0
        )
        overall_prec, overall_rec, overall_f1, _ = (
            precision_recall_fscore_support(
                all_y_true, all_y_pred, average="macro", zero_division=0
            )
            if all_y_true
            else (0.0, 0.0, 0.0, None)
        )

        # Sharpe of equity curve over walk-forward test blocks
        eq_series = pd.Series(all_equity_values)
        eq_returns = eq_series.pct_change().fillna(0.0)
        overall_return = (
            float((all_equity_values[-1] - self.initial_capital) / self.initial_capital)
            if all_equity_values
            else 0.0
        )

        # Max drawdown
        peaks = eq_series.cummax()
        drawdowns = (peaks - eq_series) / peaks
        overall_max_dd = float(drawdowns.max()) if not drawdowns.empty else 0.0

        summary_metrics = {
            "overall_accuracy": overall_accuracy,
            "overall_precision": float(overall_prec),
            "overall_recall": float(overall_rec),
            "overall_f1": float(overall_f1),
            "overall_return": overall_return,
            "overall_max_drawdown": overall_max_dd,
            "folds_completed": len(fold_results),
        }

        # Update experiment in DB with final metrics
        if pipeline_db.is_connected and experiment_id:
            try:
                async with pipeline_db.pool.acquire() as conn:
                    await conn.execute(
                        """
                        UPDATE experiments
                        SET metrics = $1
                        WHERE id = $2
                    """,
                        json.dumps(summary_metrics),
                        experiment_id,
                    )
            except Exception as e:
                logger.warning(f"Failed to update experiment metrics: {e}")

        return {
            "experiment_id": experiment_id,
            "metrics": summary_metrics,
            "folds": fold_results,
            "trades_pnl": all_realized_returns,
            "equity_curve": all_equity_values,
            "institutional_history": all_institutional_history,
            "y_true": all_y_true,
            "y_pred": all_y_pred,
            "y_prob": all_y_prob,
            "regimes": all_regimes,
        }

    def run_monte_carlo(
        self,
        trade_pnls: list[float],
        n_simulations: int = 500,
        ruin_threshold_pct: float = 0.30,
    ) -> dict:
        """
        Validates statistical edge via bootstrap trade reshuffles and Monte Carlo simulation.
        Tests the probability of ruin and p-value vs random/shuffled entries.
        """
        if not trade_pnls:
            return {
                "p_value": 1.0,
                "probability_of_ruin": 1.0,
                "expected_shortfall_95": 0.0,
                "note": "No trades executed to run simulations.",
                "n_simulations": n_simulations,
                "actual_return": 0.0,
                "statistically_significant": False,
            }

        # Terminal returns from randomized shuffles
        simulated_terminal_returns_null = []
        simulated_terminal_returns_actual = []
        ruin_count = 0

        # Array convert
        pnls = np.array(trade_pnls)
        # Center the returns under the null hypothesis (mean = 0)
        null_pnls = pnls - np.mean(pnls)

        for _ in range(n_simulations):
            # Bootstrap sample under the null hypothesis to compute p-value
            sim_pnls_null = np.random.choice(
                null_pnls, size=len(null_pnls), replace=True
            )
            terminal_return_null = np.sum(sim_pnls_null) / self.initial_capital
            simulated_terminal_returns_null.append(terminal_return_null)

            # Bootstrap sample under the actual distribution to compute VaR/CVaR and ruin probability
            sim_pnls_actual = np.random.choice(pnls, size=len(pnls), replace=True)
            equity_curve_actual = self.initial_capital + np.cumsum(sim_pnls_actual)
            terminal_return_actual = (
                equity_curve_actual[-1] - self.initial_capital
            ) / self.initial_capital
            simulated_terminal_returns_actual.append(terminal_return_actual)

            # Ruin check: drawdown below limit
            peaks = np.maximum.accumulate(equity_curve_actual)
            drawdowns = (peaks - equity_curve_actual) / peaks
            if np.max(drawdowns) > ruin_threshold_pct:
                ruin_count += 1

        # Calculate p-value: probability that a null hypothesis sequence out-performs the actual result
        actual_total_pnl = sum(trade_pnls)
        actual_return = actual_total_pnl / self.initial_capital

        better_sims = sum(
            1 for r in simulated_terminal_returns_null if r >= actual_return
        )
        p_value = float(better_sims / n_simulations)

        # Probability of ruin
        prob_ruin = float(ruin_count / n_simulations)

        # Expected Shortfall (CVaR at 95% confidence) based on actual bootstrap distribution
        simulated_terminal_returns_actual = np.array(simulated_terminal_returns_actual)
        var_95 = np.percentile(simulated_terminal_returns_actual, 5)
        expected_shortfall = float(
            np.mean(
                simulated_terminal_returns_actual[
                    simulated_terminal_returns_actual <= var_95
                ]
            )
        )

        return {
            "p_value": p_value,
            "probability_of_ruin": prob_ruin,
            "expected_shortfall_95": expected_shortfall,
            "statistically_significant": p_value < 0.05,
            "n_simulations": n_simulations,
            "actual_return": actual_return,
        }
