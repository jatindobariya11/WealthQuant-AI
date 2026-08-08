"""
WealthQuant Backtesting Engine — PostgreSQL Data Loader
Loads ALL historical data exclusively from PostgreSQL. Zero API calls.
Tables: ohlcv_history, predictions, signal_explanations, regime_history,
        options_intelligence, fii_dii, feature_alpha_rankings,
        walk_forward_results, stage_contributions
"""

import asyncio
import logging
from datetime import timedelta

import pandas as pd

logger = logging.getLogger("backtest.data_loader")


class BacktestDataLoader:
    def __init__(self, db):
        self.db = db

    async def load_ohlcv(self, symbol: str, timeframe: str = "15m") -> pd.DataFrame:
        if not self.db.pool:
            raise RuntimeError("Database pool not connected.")
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT timestamp, open, high, low, close, volume "
                "FROM ohlcv_history WHERE symbol = $1 AND timeframe = $2 "
                "ORDER BY timestamp ASC",
                symbol.upper(),
                timeframe,
            )
        if not rows:
            logger.warning(f"[DataLoader] No OHLCV for {symbol}/{timeframe}")
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        logger.info(
            f"[DataLoader] {len(df)} OHLCV bars for {symbol}/{timeframe} "
            f"({df.index[0].date()} to {df.index[-1].date()})"
        )
        return df

    async def load_predictions(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT timestamp, horizon, p_up, p_down, p_sideways, "
                "expected_return, signal, signal_confidence, regime, "
                "kelly_fraction, actual_return, was_correct "
                "FROM predictions WHERE symbol = $1 ORDER BY timestamp ASC",
                symbol.upper(),
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        logger.info(f"[DataLoader] {len(df)} predictions for {symbol}")
        return df

    async def load_signal_explanations(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT timestamp, spot_price, hawkes_score, kalman_velocity, "
                "particle_mean, regime_state, ensemble_prediction, "
                "meta_learning_weight, fusion_mean, p_up, p_down, "
                "expected_return, kelly_fraction, signal, signal_confidence, "
                "actual_return, correct, institutional_forecast, "
                "institutional_confidence, positioning_strength, "
                "bullish_score, bearish_score, neutral_score, "
                "pcr_val, gamma_pressure, dealer_pressure "
                "FROM signal_explanations WHERE symbol = $1 ORDER BY timestamp ASC",
                symbol.upper(),
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        logger.info(f"[DataLoader] {len(df)} signal explanations for {symbol}")
        return df

    async def load_regime_history(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT start_time, end_time, regime, confidence, duration_bars "
                "FROM regime_history WHERE symbol = $1 ORDER BY start_time ASC",
                symbol.upper(),
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["start_time"] = pd.to_datetime(df["start_time"], utc=True)
        df = df.set_index("start_time").sort_index()
        logger.info(f"[DataLoader] {len(df)} regime records for {symbol}")
        return df

    async def load_options_intelligence(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT timestamp, pcr, pcr_momentum, oi_velocity, oi_momentum, "
                "volume_oi_ratio, call_wall, put_wall, support_strength, "
                "resistance_strength, atm_iv, gamma_pressure, dealer_pressure, "
                "forecast, confidence, positioning_strength "
                "FROM options_intelligence WHERE symbol = $1 ORDER BY timestamp ASC",
                symbol.upper(),
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp").sort_index()
        df = df[~df.index.duplicated(keep="last")]
        logger.info(f"[DataLoader] {len(df)} options records for {symbol}")
        return df

    async def load_fii_dii(self) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT date, fii_net, dii_net FROM fii_dii ORDER BY date ASC"
            )
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame([dict(r) for r in rows])
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.set_index("date").sort_index()
        logger.info(f"[DataLoader] {len(df)} FII/DII records")
        return df

    async def load_feature_alpha_rankings(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT horizon, feature_name, correlation, p_value, "
                "information_ratio, composite_score, rank "
                "FROM feature_alpha_rankings WHERE symbol = $1 ORDER BY rank ASC",
                symbol.upper(),
            )
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    async def load_walk_forward_results(self) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT wfr.fold_index, wfr.train_start, wfr.train_end, "
                "wfr.test_start, wfr.test_end, wfr.accuracy, wfr.precision_val, "
                "wfr.recall_val, wfr.f1_score, wfr.sharpe_ratio, wfr.max_drawdown, "
                "e.name as experiment_name "
                "FROM walk_forward_results wfr "
                "LEFT JOIN experiments e ON e.id = wfr.experiment_id "
                "ORDER BY wfr.created_at DESC LIMIT 50"
            )
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    async def load_stage_contributions(self, symbol: str) -> pd.DataFrame:
        if not self.db.pool:
            return pd.DataFrame()
        async with self.db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT stage, accuracy, correlation, mae, sharpe_contribution, "
                "drawdown_contribution, status "
                "FROM stage_contributions WHERE symbol = $1 "
                "ORDER BY sharpe_contribution DESC NULLS LAST",
                symbol.upper(),
            )
        return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()

    async def load_all_table_counts(self) -> dict:
        tables = [
            "predictions",
            "prediction_history",
            "prediction_results",
            "prediction_accuracy",
            "signal_explanations",
            "stage_contributions",
            "ablation_results",
            "regime_performance",
            "feature_drift",
            "alpha_leaderboard",
            "experiments",
            "walk_forward_results",
            "ohlcv_history",
            "feature_store",
            "regime_history",
            "model_accuracy",
            "backtests",
            "fii_dii",
            "options_intelligence",
            "options_history",
            "strike_history",
            "wall_history",
            "pcr_history",
            "feature_alpha_rankings",
        ]
        counts = {}
        if not self.db.pool:
            return counts
        async with self.db.pool.acquire() as conn:
            for table in tables:
                try:
                    row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {table}")
                    counts[table] = int(row["cnt"]) if row else 0
                except Exception:
                    counts[table] = -1
        return counts

    # --- Alignment helpers ---

    def align_options_to_ohlcv(self, ohlcv_df, options_df):
        """Forward-fill options to OHLCV timestamps — no lookahead."""
        if options_df.empty:
            return pd.DataFrame(index=ohlcv_df.index)
        combined_index = ohlcv_df.index.union(options_df.index).sort_values()
        return options_df.reindex(combined_index).ffill().reindex(ohlcv_df.index)

    def map_regime_to_ohlcv(self, ohlcv_df, regime_df):
        """Map regime history labels to each OHLCV bar — no lookahead."""
        if regime_df.empty:
            return pd.Series("UNKNOWN", index=ohlcv_df.index)
        regime_series = regime_df["regime"]
        combined_index = ohlcv_df.index.union(regime_series.index).sort_values()
        return (
            regime_series.reindex(combined_index)
            .ffill()
            .fillna("UNKNOWN")
            .reindex(ohlcv_df.index)
            .fillna("UNKNOWN")
        )

    def align_fii_to_ohlcv(self, ohlcv_df, fii_df):
        """Align daily FII/DII flows to intraday OHLCV bars by date."""
        if fii_df.empty:
            return pd.DataFrame({"fii_net": 0.0, "dii_net": 0.0}, index=ohlcv_df.index)
        fii_map = fii_df[["fii_net", "dii_net"]].to_dict(orient="index")
        fii_net = [
            fii_map.get(ts.date(), {}).get("fii_net", 0.0) for ts in ohlcv_df.index
        ]
        dii_net = [
            fii_map.get(ts.date(), {}).get("dii_net", 0.0) for ts in ohlcv_df.index
        ]
        return pd.DataFrame(
            {"fii_net": fii_net, "dii_net": dii_net}, index=ohlcv_df.index
        )

    # --- Master bundle loader ---

    async def load_backtest_bundle(self, symbol: str, timeframe: str = "15m") -> dict:
        """Load and align ALL data required for backtesting in one call."""
        logger.info(
            f"[DataLoader] Loading full backtest bundle for {symbol}/{timeframe}..."
        )
        results = await asyncio.gather(
            self.load_ohlcv(symbol, timeframe),
            self.load_predictions(symbol),
            self.load_signal_explanations(symbol),
            self.load_regime_history(symbol),
            self.load_options_intelligence(symbol),
            self.load_fii_dii(),
            self.load_feature_alpha_rankings(symbol),
            self.load_walk_forward_results(),
            self.load_stage_contributions(symbol),
        )
        (
            ohlcv,
            predictions,
            signal_expl,
            regime_hist,
            options,
            fii,
            rankings,
            wfr,
            stage_contribs,
        ) = results
        if ohlcv.empty:
            raise ValueError(
                f"No OHLCV data for {symbol}/{timeframe} in PostgreSQL. "
                "Ensure the ingestion scheduler has run."
            )
        bundle = {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "ohlcv": ohlcv,
            "predictions": predictions,
            "signal_explanations": signal_expl,
            "regime_labels": self.map_regime_to_ohlcv(ohlcv, regime_hist),
            "options": self.align_options_to_ohlcv(ohlcv, options),
            "options_raw": options,
            "fii_dii": self.align_fii_to_ohlcv(ohlcv, fii),
            "fii_dii_raw": fii,
            "feature_rankings": rankings,
            "walk_forward_results": wfr,
            "stage_contributions": stage_contribs,
        }
        logger.info(
            f"[DataLoader] Bundle ready: {len(ohlcv)} bars, "
            f"{len(predictions)} preds, {len(options)} options"
        )
        return bundle

    # --- Data quality audit ---

    def audit_data_quality(self, bundle: dict) -> dict:
        """Comprehensive data quality check on the loaded bundle."""
        ohlcv = bundle["ohlcv"]
        predictions = bundle["predictions"]
        options_raw = bundle["options_raw"]
        fii_raw = bundle["fii_dii_raw"]
        symbol = bundle["symbol"]
        timeframe = bundle["timeframe"]
        issues = []
        stats = {}

        # 1. Gap detection
        if len(ohlcv) > 1:
            tf_map = {
                "15m": timedelta(minutes=15),
                "1h": timedelta(hours=1),
                "1d": timedelta(days=1),
            }
            expected = tf_map.get(timeframe, timedelta(minutes=15))
            diffs = ohlcv.index.to_series().diff().dropna()
            gaps = diffs[diffs > expected * 2]
            stats["ohlcv_total_bars"] = len(ohlcv)
            stats["ohlcv_missing_candles"] = len(gaps)
            trading_days = len(set(d.date() for d in ohlcv.index))
            stats["ohlcv_date_range"] = (
                str(ohlcv.index[0].date()) + " to " + str(ohlcv.index[-1].date())
            )
            stats["ohlcv_trading_days"] = trading_days
            if len(gaps) > 0:
                issues.append(f"{len(gaps)} candle gaps in {symbol} {timeframe}")

        # 2. Duplicates
        ohlcv_dups = int(ohlcv.index.duplicated().sum())
        pred_dups = (
            int(predictions.index.duplicated().sum()) if not predictions.empty else 0
        )
        stats["ohlcv_duplicates"] = ohlcv_dups
        stats["prediction_duplicates"] = pred_dups
        if ohlcv_dups > 0:
            issues.append(f"{ohlcv_dups} duplicate OHLCV timestamps")

        # 3. Prediction coverage
        stats["total_predictions"] = len(predictions)
        if not predictions.empty and not ohlcv.empty:
            matched = predictions.index.isin(ohlcv.index)
            stats["predictions_with_ohlcv_match"] = int(matched.sum())
            stats["prediction_gaps"] = int((~matched).sum())
            if stats["prediction_gaps"] > 0:
                issues.append(
                    f"{stats['prediction_gaps']} predictions without OHLCV match"
                )

        # 4. Options coverage
        if not options_raw.empty and not ohlcv.empty:
            cov = round(len(options_raw) / len(ohlcv) * 100, 1)
            stats["options_coverage_pct"] = cov
            stats["options_total_records"] = len(options_raw)
            if cov < 50:
                issues.append(f"Low options coverage: {cov}%")
        else:
            stats["options_coverage_pct"] = 0.0
            stats["options_total_records"] = 0
            issues.append("No options intelligence data")

        # 5. FII/DII coverage
        if not fii_raw.empty and not ohlcv.empty:
            trading_days = len(set(d.date() for d in ohlcv.index))
            fii_days = len(fii_raw)
            fii_cov = round(fii_days / trading_days * 100, 1) if trading_days > 0 else 0
            stats["fii_dii_trading_days"] = trading_days
            stats["fii_dii_available_days"] = fii_days
            stats["fii_dii_coverage_pct"] = fii_cov
            if fii_cov < 80:
                issues.append(f"Incomplete FII/DII: {fii_days}/{trading_days} days")
        else:
            stats["fii_dii_coverage_pct"] = 0.0
            stats["fii_dii_available_days"] = 0
            issues.append("No FII/DII data")

        # 6. Prediction evaluation status
        if not predictions.empty:
            evaluated = predictions["was_correct"].dropna()
            stats["predictions_evaluated"] = len(evaluated)
            stats["predictions_pending_evaluation"] = len(predictions) - len(evaluated)
            stats["raw_accuracy"] = (
                round(float(evaluated.mean()) * 100, 1) if len(evaluated) > 0 else None
            )

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "issues": issues,
            "issue_count": len(issues),
            "quality_grade": (
                "PASS" if len(issues) == 0 else "WARN" if len(issues) <= 3 else "FAIL"
            ),
            "stats": stats,
        }
