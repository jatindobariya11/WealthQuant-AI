"""
Pipeline Orchestrator.
Chains all 10 pipeline stages, tracks latencies, handles errors, and persists results.
"""

import asyncio
import concurrent.futures
import functools
import os

QUANT_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(4, (os.cpu_count() or 4) * 2), thread_name_prefix="quant_engine"
)


async def _run_quant(func, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        QUANT_EXECUTOR, functools.partial(func, *args, **kwargs)
    )


import logging
import time
from datetime import datetime

import pandas as pd

from pipeline.base import MarketSnapshot, PipelineResult
from pipeline.db import pipeline_db
from pipeline.explainability import SignalExplainabilityManager
from pipeline.institutional_engine import Stage5_5Institutional
from pipeline.stage1_market_adapter import Stage1MarketAdapter
from pipeline.stage2_hawkes import Stage2Hawkes
from pipeline.stage3_kalman import Stage3Kalman
from pipeline.stage4_particle import Stage4Particle
from pipeline.stage5_regime import Stage5Regime
from pipeline.stage6_ensemble import Stage6Ensemble
from pipeline.stage7_meta_learning import Stage7MetaLearning
from pipeline.stage8_bayesian_fusion import Stage8BayesianFusion
from pipeline.stage9_probability_engine import Stage9ProbabilityEngine
from pipeline.stage10_llm_analyst import Stage10LLMAnalyst

logger = logging.getLogger("pipeline.orchestrator")


class PipelineOrchestrator:
    def __init__(self):
        # Instantiate all stages
        self.stage1 = Stage1MarketAdapter()
        self.stage2 = Stage2Hawkes()
        self.stage3 = Stage3Kalman()
        self.stage4 = Stage4Particle()
        self.stage5 = Stage5Regime()
        self.stage5_5 = Stage5_5Institutional()
        self.stage6 = Stage6Ensemble()
        self.stage7 = Stage7MetaLearning()
        self.stage8 = Stage8BayesianFusion()
        self.stage9 = Stage9ProbabilityEngine()
        self.stage10 = Stage10LLMAnalyst()
        self.explainability = SignalExplainabilityManager()

    async def run(
        self, symbol: str, interval: str = "15m", skip_llm: bool = False
    ) -> PipelineResult:
        """
        Run the full 10-stage probabilistic AI pipeline.
        """
        t_start = time.perf_counter()

        stage_latencies = {}
        errors = {}

        # ─── Stage 1: Market Data Adapter ───
        t_s = time.perf_counter()
        try:
            snapshot = await _run_quant(self.stage1.process, symbol, interval)
            stage_latencies["market_adapter"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            logger.error(f"Stage 1 Market Adapter failed: {e}")
            raise

        # ─── Stages 2-4: Parallel Statistical Core ───
        t_s = time.perf_counter()

        async def run_hawkes():
            try:
                t0 = time.perf_counter()
                res = await _run_quant(self.stage2.process, snapshot)
                stage_latencies["hawkes"] = (time.perf_counter() - t0) * 1000.0
                return res
            except Exception as e:
                errors["hawkes"] = str(e)
                logger.error(f"Stage 2 Hawkes failed: {e}")
                return self.stage2.timed_process(snapshot)[
                    0
                ]  # try again or returns defaults

        async def run_kalman():
            try:
                t0 = time.perf_counter()
                res = await _run_quant(self.stage3.process, snapshot)
                stage_latencies["kalman"] = (time.perf_counter() - t0) * 1000.0
                return res
            except Exception as e:
                errors["kalman"] = str(e)
                logger.error(f"Stage 3 Kalman failed: {e}")
                raise

        async def run_particle():
            try:
                t0 = time.perf_counter()
                res = await _run_quant(self.stage4.process, snapshot)
                stage_latencies["particle"] = (time.perf_counter() - t0) * 1000.0
                return res
            except Exception as e:
                errors["particle"] = str(e)
                logger.error(f"Stage 4 Particle failed: {e}")
                raise

        # Execute parallel group
        try:
            hawkes, kalman, particle = await asyncio.gather(
                run_hawkes(), run_kalman(), run_particle()
            )
        except Exception as e:
            logger.error(f"Parallel statistical filters failed: {e}")
            raise

        # ─── Stage 5: Regime Detection ───
        t_s = time.perf_counter()
        try:
            regime = await _run_quant(self.stage5.process, snapshot, kalman, particle)
            stage_latencies["regime"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["regime"] = str(e)
            logger.error(f"Stage 5 Regime Detection failed: {e}")
            raise

        # ─── Stage 5.5: Institutional Positioning Engine ───
        t_s = time.perf_counter()
        try:
            institutional = await _run_quant(self.stage5_5.process, snapshot, regime)
            stage_latencies["institutional"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["institutional"] = str(e)
            logger.error(f"Stage 5.5 Institutional Positioning failed: {e}")
            raise

        # ─── Stage 6: Ensemble Predictor ───
        t_s = time.perf_counter()
        try:
            ensemble = await _run_quant(
                self.stage6.process, snapshot, hawkes, kalman, particle, regime
            )
            stage_latencies["ensemble"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["ensemble"] = str(e)
            logger.error(f"Stage 6 Ensemble Predictor failed: {e}")
            raise

        # ─── Stage 7: Meta-Learning ───
        t_s = time.perf_counter()
        try:
            meta_learning = await _run_quant(
                self.stage7.process, ensemble, regime, symbol=snapshot.symbol
            )
            stage_latencies["meta_learning"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["meta_learning"] = str(e)
            logger.error(f"Stage 7 Meta-Learning failed: {e}")
            raise

        # ─── Stage 8: Bayesian Fusion ───
        t_s = time.perf_counter()
        try:
            price = snapshot.ohlcv["close"].values[-1]
            fusion = await _run_quant(
                self.stage8.process,
                price,
                hawkes,
                kalman,
                particle,
                meta_learning,
                regime,
                institutional,
            )
            stage_latencies["bayesian_fusion"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["bayesian_fusion"] = str(e)
            logger.error(f"Stage 8 Bayesian Fusion failed: {e}")
            raise

        # ─── Stage 9: Probability Engine ───
        t_s = time.perf_counter()
        try:
            # Periodically refit calibrators to include newly evaluated predictions
            if pipeline_db.is_connected:
                calib_up = self.stage9._get_calibrator(symbol, "up")
                if not hasattr(self.stage9, "_run_count"):
                    self.stage9._run_count = 0

                # Fit on first run, or every 20 runs (~5 minutes if refresh interval is 15s)
                if not calib_up.is_fitted or self.stage9._run_count % 20 == 0:
                    try:
                        await self.stage9.fit_calibrators(symbol)
                    except Exception as calib_err:
                        logger.warning(
                            f"Failed to fit calibrators for {symbol}: {calib_err}"
                        )

                self.stage9._run_count += 1

            probabilities = await _run_quant(
                self.stage9.process, symbol, fusion, regime
            )
            stage_latencies["probability_engine"] = (time.perf_counter() - t_s) * 1000.0
        except Exception as e:
            errors["probability_engine"] = str(e)
            logger.error(f"Stage 9 Probability Engine failed: {e}")
            raise

        # ─── Construct intermediate result for LLM ───
        total_latency_ms = (time.perf_counter() - t_start) * 1000.0

        result = PipelineResult(
            symbol=symbol.upper(),
            timestamp=snapshot.timestamp,
            interval=interval,
            hawkes=hawkes,
            kalman=kalman,
            particle=particle,
            regime=regime,
            institutional=institutional,
            ensemble=ensemble,
            meta_learning=meta_learning,
            fusion=fusion,
            probabilities=probabilities,
            analyst_report=None,
            latency_ms=total_latency_ms,
            stage_latencies=stage_latencies,
            errors=errors,
        )

        # ─── Stage 10: LLM Analyst ───
        if not skip_llm:
            t_s = time.perf_counter()
            try:
                analyst_report = await _run_quant(
                    self.stage10.process, symbol, price, result.to_dict()
                )
                result.analyst_report = analyst_report
                stage_latencies["llm_analyst"] = (time.perf_counter() - t_s) * 1000.0
            except Exception as e:
                errors["llm_analyst"] = str(e)
                logger.error(f"Stage 10 LLM Analyst failed: {e}")

        # Re-calc final total latency
        result.latency_ms = (time.perf_counter() - t_start) * 1000.0
        result.stage_latencies = stage_latencies
        result.errors = errors

        # ─── 11. Async Database and Explainability Persistence ───
        # Fire-and-forget saving to PostgreSQL and local CSV reports
        asyncio.create_task(self._persist_to_db(result, snapshot))
        asyncio.create_task(
            self._evaluate_predictions(symbol, interval, snapshot.ohlcv)
        )

        return result

    async def _persist_to_db(self, result: PipelineResult, snapshot: MarketSnapshot):
        """
        Background task to save pipeline predictions to PostgreSQL and explainability reports.
        """
        # Record explainability predictions (always runs, has local CSV fallback)
        try:
            await self.explainability.record_prediction(result, snapshot)
        except Exception as exp_err:
            logger.warning(f"Failed to record explainability metrics: {exp_err}")

        # Standard database persistence if connected
        if pipeline_db.is_connected:
            try:
                # 1. Prepare prediction
                pred_record = {
                    "symbol": result.symbol,
                    "timestamp": result.timestamp,
                    "horizon": "5",  # standard default horizon
                    "p_up": result.probabilities.p_up,
                    "p_down": result.probabilities.p_down,
                    "p_sideways": result.probabilities.p_sideways,
                    "expected_return": result.probabilities.expected_return,
                    "signal": result.probabilities.signal,
                    "signal_confidence": result.probabilities.signal_confidence,
                    "regime": result.regime.current_regime,
                    "model_weights": result.fusion.model_weights,
                    "kelly_fraction": result.probabilities.kelly_fraction,
                }

                # 2. Prepare options intelligence
                opt_record = None
                if result.institutional:
                    opt_record = {
                        "symbol": result.symbol,
                        "timestamp": result.timestamp,
                        "pcr": result.institutional.pcr,
                        "pcr_momentum": result.institutional.pcr_momentum,
                        "oi_velocity": result.institutional.oi_velocity,
                        "oi_momentum": result.institutional.oi_momentum,
                        "volume_oi_ratio": result.institutional.volume_oi_ratio,
                        "strike_migration": result.institutional.strike_migration,
                        "call_wall": result.institutional.call_wall,
                        "put_wall": result.institutional.put_wall,
                        "support_strength": result.institutional.support_strength,
                        "resistance_strength": result.institutional.resistance_strength,
                        "atm_iv": result.institutional.atm_iv,
                        "gamma_pressure": result.institutional.gamma_pressure,
                        "dealer_pressure": result.institutional.dealer_pressure,
                        "forecast": result.institutional.forecast,
                        "confidence": result.institutional.confidence,
                        "positioning_strength": result.institutional.positioning_strength,
                        "call_chain": snapshot.options.get("strikes")
                        if isinstance(snapshot.options, dict)
                        else None,
                        "put_chain": snapshot.options.get("strikes")
                        if isinstance(snapshot.options, dict)
                        else None,
                    }

                # 3. Prepare regime segment
                regime_record = {
                    "symbol": result.symbol,
                    "regime": result.regime.current_regime,
                    "start_time": result.timestamp,
                    "confidence": result.regime.regime_confidence,
                    "duration_bars": result.regime.regime_duration_bars,
                    "features": result.regime.features_used,
                }

                # Execute batched transactional insert
                await pipeline_db.insert_pipeline_results_transactional(
                    pred=pred_record, opt=opt_record, regime=regime_record
                )

            except Exception as db_err:
                logger.warning(f"Background database persistence failed: {db_err}")

    async def _evaluate_predictions(
        self, symbol: str, interval: str, ohlcv_df: pd.DataFrame
    ):
        """
        Evaluate completed predictions using current snapshot OHLCV dataframe.
        """
        try:
            evaluated_count = 0
            symbol_upper = symbol.upper()

            # 1. Database-backed evaluation
            if pipeline_db.is_connected:
                predictions = await pipeline_db.get_unevaluated_predictions(
                    symbol_upper, limit=50
                )
                for pred in predictions:
                    pred_id = pred["id"]
                    pred_ts = pred["timestamp"]
                    horizon = int(pred.get("horizon", "5"))  # default 5 bars

                    # Convert prediction timestamp to naive datetime
                    pred_dt = pred_ts
                    if hasattr(pred_dt, "tzinfo") and pred_dt.tzinfo is not None:
                        pred_dt = pred_dt.replace(tzinfo=None)

                    # Try exact string lookup
                    dt_str = pred_dt.strftime("%Y-%m-%d %H:%M:%S")
                    idx = None
                    if dt_str in ohlcv_df.index:
                        idx = ohlcv_df.index.get_loc(dt_str)
                    else:
                        # Fallback: parse index strings and find closest match within 10 seconds
                        for pos, idx_val in enumerate(ohlcv_df.index):
                            try:
                                idx_dt = datetime.strptime(idx_val, "%Y-%m-%d %H:%M:%S")
                            except ValueError:
                                try:
                                    idx_dt = datetime.strptime(idx_val, "%Y-%m-%d")
                                except ValueError:
                                    continue

                            if abs((idx_dt - pred_dt).total_seconds()) < 10:
                                idx = pos
                                break

                    if idx is not None and idx + horizon < len(ohlcv_df):
                        price_start = ohlcv_df.iloc[idx]["close"]
                        price_end = ohlcv_df.iloc[idx + horizon]["close"]

                        if price_start > 0:
                            actual_return = (price_end - price_start) / price_start
                            # Update standard prediction DB table
                            await pipeline_db.update_prediction_outcome(
                                pred_id, actual_return
                            )
                            # Update explainability DB and CSV
                            await self.explainability.update_and_analyze(
                                symbol_upper, pred_ts, actual_return
                            )
                            evaluated_count += 1

            # 2. Local CSV-backed evaluation sync (runs always to keep CSV evaluated and updated)
            if os.path.exists(self.explainability.debug_report_path):
                try:
                    df = pd.read_csv(self.explainability.debug_report_path)
                    unevaluated = df[
                        (df["symbol"] == symbol_upper) & (df["actual_return"].isna())
                    ]
                    for _, row in unevaluated.iterrows():
                        ts_val = row["timestamp"]
                        try:
                            pred_dt = pd.to_datetime(ts_val)
                            if hasattr(pred_dt, "to_pydatetime"):
                                pred_dt = pred_dt.to_pydatetime()
                            if pred_dt.tzinfo is not None:
                                pred_dt = pred_dt.replace(tzinfo=None)
                        except Exception:
                            continue

                        dt_str = pred_dt.strftime("%Y-%m-%d %H:%M:%S")
                        idx = None
                        if dt_str in ohlcv_df.index:
                            idx = ohlcv_df.index.get_loc(dt_str)
                        else:
                            for pos, idx_val in enumerate(ohlcv_df.index):
                                try:
                                    idx_dt = datetime.strptime(
                                        idx_val, "%Y-%m-%d %H:%M:%S"
                                    )
                                except ValueError:
                                    try:
                                        idx_dt = datetime.strptime(idx_val, "%Y-%m-%d")
                                    except ValueError:
                                        continue
                                if abs((idx_dt - pred_dt).total_seconds()) < 10:
                                    idx = pos
                                    break

                        horizon = 5  # default horizon
                        if idx is not None and idx + horizon < len(ohlcv_df):
                            price_start = ohlcv_df.iloc[idx]["close"]
                            price_end = ohlcv_df.iloc[idx + horizon]["close"]
                            if price_start > 0:
                                actual_return = (price_end - price_start) / price_start
                                # Update and analyze explainability
                                await self.explainability.update_and_analyze(
                                    symbol_upper, pred_dt, actual_return
                                )
                                evaluated_count += 1
                except Exception as csv_eval_err:
                    logger.warning(
                        f"Error evaluating local predictions in CSV: {csv_eval_err}"
                    )

            if evaluated_count > 0:
                logger.info(
                    f"Evaluated {evaluated_count} completed predictions for {symbol}."
                )

        except Exception as eval_err:
            logger.warning(f"Error evaluating predictions: {eval_err}")

    def get_status(self) -> dict:
        """
        Get statuses of all pipeline stages.
        """
        return {
            "orchestrator": "active",
            "database_connected": pipeline_db.is_connected,
            "stages": {
                "market_adapter": self.stage1.health_check(),
                "hawkes": self.stage2.health_check(),
                "kalman": self.stage3.health_check(),
                "particle": self.stage4.health_check(),
                "regime": self.stage5.health_check(),
                "ensemble": self.stage6.health_check(),
                "meta_learning": self.stage7.health_check(),
                "bayesian_fusion": self.stage8.health_check(),
                "probability_engine": self.stage9.health_check(),
                "llm_analyst": self.stage10.health_check(),
            },
        }
