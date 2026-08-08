"""
WealthQuant V9.1 — Alpha Discovery Engine: Data Loader
=======================================================
Loads all research inputs from PostgreSQL for the Alpha Discovery Engine.
Read-only. Zero writes to any production table.

Supported data sources:
  - OHLCV history (ohlcv_history)
  - Options history (warehouse_options_daily / options_chain_snapshots)
  - Strike history (strike_history)
  - Wall history (wall_history)
  - PCR history (pcr_history)
  - Market snapshots (market_snapshots)
  - FII/DII data (fii_dii_data)
  - Research feature evaluations (research_feature_evaluations)
"""

import asyncio
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger("alpha.data_loader")

# ── Supported symbols and intervals ───────────────────────────────────────────
SUPPORTED_SYMBOLS = ["NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY"]
SUPPORTED_INTERVALS = ["1d", "1h", "15m", "5m"]


class AlphaDataLoader:
    """
    Read-only data loader for the Alpha Discovery Engine.
    All methods return pandas DataFrames or Series.
    All operations are read-only on production tables.
    """

    def __init__(self, pool):
        """
        Args:
            pool: asyncpg connection pool (from pipeline_db.pool)
        """
        self.pool = pool

    # ── OHLCV ─────────────────────────────────────────────────────────────────

    async def load_ohlcv(
        self,
        symbol: str,
        interval: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        min_rows: int = 60,
    ) -> pd.DataFrame:
        """
        Load OHLCV data from ohlcv_history.

        Returns DataFrame with columns:
            timestamp, open, high, low, close, volume
            ret_1d, ret_3d, ret_5d, ret_10d  (forward returns — research targets)
        """
        if self.pool is None:
            return self._empty_ohlcv()

        query = """
            SELECT
                timestamp::date   AS date,
                open, high, low, close, volume
            FROM ohlcv_history
            WHERE symbol = $1
              AND interval = $2
              {date_filter}
            ORDER BY timestamp ASC
        """
        date_filter = ""
        params = [symbol, interval]
        if start_date:
            params.append(start_date)
            date_filter += f" AND timestamp::date >= ${len(params)}"
        if end_date:
            params.append(end_date)
            date_filter += f" AND timestamp::date <= ${len(params)}"

        query = query.format(date_filter=date_filter)

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            if not rows or len(rows) < min_rows:
                logger.warning(
                    f"[DataLoader] {symbol}/{interval}: only {len(rows) if rows else 0} rows "
                    f"(minimum {min_rows}). Skipping."
                )
                return self._empty_ohlcv()

            df = pd.DataFrame(
                rows, columns=["date", "open", "high", "low", "close", "volume"]
            )
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)
            df["volume"] = df["volume"].fillna(0)

            # Compute forward returns (research targets — not used in production)
            close = df["close"]
            df["ret_1d"] = close.pct_change(1).shift(-1)
            df["ret_3d"] = close.pct_change(3).shift(-3)
            df["ret_5d"] = close.pct_change(5).shift(-5)
            df["ret_10d"] = close.pct_change(10).shift(-10)
            df["ret_prev_1d"] = close.pct_change(1)  # backward return

            logger.info(
                f"[DataLoader] Loaded {len(df)} OHLCV rows for {symbol}/{interval}"
            )
            return df

        except Exception as e:
            logger.error(f"[DataLoader] OHLCV load failed for {symbol}: {e}")
            return self._empty_ohlcv()

    def _empty_ohlcv(self) -> pd.DataFrame:
        cols = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "ret_1d",
            "ret_3d",
            "ret_5d",
            "ret_10d",
            "ret_prev_1d",
        ]
        return pd.DataFrame(columns=cols)

    # ── OI / Strike ────────────────────────────────────────────────────────────

    async def load_strike_oi_daily(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Load aggregated daily OI from strike_history.

        Returns DataFrame indexed by date with columns:
            total_oi, call_oi, put_oi, call_volume, put_volume
            oi_velocity_1d, oi_velocity_5d, pcr_oi, call_cog, put_cog
        """
        if self.pool is None:
            return pd.DataFrame()

        query = """
            SELECT
                date,
                SUM(call_oi)     AS call_oi,
                SUM(put_oi)      AS put_oi,
                SUM(call_oi + put_oi) AS total_oi,
                SUM(call_volume) AS call_volume,
                SUM(put_volume)  AS put_volume,
                SUM(strike * call_oi) / NULLIF(SUM(call_oi),0) AS call_cog,
                SUM(strike * put_oi)  / NULLIF(SUM(put_oi),0)  AS put_cog
            FROM strike_history
            WHERE symbol = $1
              {date_filter}
            GROUP BY date
            ORDER BY date ASC
        """
        params = [symbol]
        date_filter = ""
        if start_date:
            params.append(start_date)
            date_filter += f" AND date >= ${len(params)}"
        if end_date:
            params.append(end_date)
            date_filter += f" AND date <= ${len(params)}"

        query = query.format(date_filter=date_filter)

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)

            # Derived features
            df["pcr_oi"] = df["put_oi"] / df["call_oi"].replace(0, np.nan)
            df["oi_velocity_1d"] = df["total_oi"].diff(1)
            df["oi_velocity_5d"] = df["total_oi"].diff(5)
            df["oi_acceleration"] = df["oi_velocity_1d"].diff(1)

            # OI momentum (z-score, 60-day rolling)
            roll_mean = df["total_oi"].rolling(60).mean()
            roll_std = df["total_oi"].rolling(60).std()
            df["oi_zscore"] = (df["total_oi"] - roll_mean) / roll_std.replace(0, np.nan)

            # COG migration
            df["call_cog_migration"] = df["call_cog"].diff(1)
            df["put_cog_migration"] = df["put_cog"].diff(1)
            df["cog_spread"] = df["call_cog"] - df["put_cog"]

            logger.info(f"[DataLoader] Loaded {len(df)} strike OI rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"[DataLoader] Strike OI load failed: {e}")
            return pd.DataFrame()

    async def load_oi_entropy_daily(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.Series:
        """Compute daily OI Shannon entropy from strike_history."""
        if self.pool is None:
            return pd.Series(dtype=float)

        query = """
            SELECT
                date,
                strike,
                (call_oi + put_oi) AS oi
            FROM strike_history
            WHERE symbol = $1
              AND (call_oi + put_oi) > 0
            {date_filter}
            ORDER BY date, strike
        """
        params = [symbol]
        date_filter = ""
        if start_date:
            params.append(start_date)
            date_filter += f" AND date >= ${len(params)}"
        if end_date:
            params.append(end_date)
            date_filter += f" AND date <= ${len(params)}"

        query = query.format(date_filter=date_filter)

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, *params)

            if not rows:
                return pd.Series(dtype=float)

            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])

            def _entropy(group):
                oi = group["oi"].values.astype(float)
                total = oi.sum()
                if total == 0:
                    return np.nan
                p = oi / total
                p = p[p > 0]
                return -np.sum(p * np.log2(p))

            entropy = df.groupby("date").apply(_entropy)
            entropy.name = "oi_entropy"
            return entropy

        except Exception as e:
            logger.error(f"[DataLoader] OI entropy computation failed: {e}")
            return pd.Series(dtype=float)

    # ── PCR ───────────────────────────────────────────────────────────────────

    async def load_pcr_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Load PCR history from pcr_history table.

        Returns DataFrame with:
            pcr_oi, pcr_vol, pcr_zscore_60d, pcr_momentum_5d, pcr_acceleration
        """
        if self.pool is None:
            return pd.DataFrame()

        query = """
            SELECT date, pcr_oi, pcr_vol
            FROM pcr_history
            WHERE symbol = $1
            {date_filter}
            ORDER BY date ASC
        """
        params = [symbol]
        date_filter = ""
        if start_date:
            params.append(start_date)
            date_filter += f" AND date >= ${len(params)}"
        if end_date:
            params.append(end_date)
            date_filter += f" AND date <= ${len(params)}"

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query.format(date_filter=date_filter), *params)

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)

            # PCR z-score (60d rolling)
            roll = df["pcr_oi"].rolling(60)
            df["pcr_zscore_60d"] = (df["pcr_oi"] - roll.mean()) / roll.std().replace(
                0, np.nan
            )
            df["pcr_momentum_5d"] = df["pcr_oi"].diff(5)
            df["pcr_acceleration"] = df["pcr_oi"].diff(1).diff(1)
            df["pcr_pct_60d"] = df["pcr_oi"].rank(pct=True, method="average")

            logger.info(f"[DataLoader] Loaded {len(df)} PCR rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"[DataLoader] PCR load failed: {e}")
            return pd.DataFrame()

    # ── Wall ──────────────────────────────────────────────────────────────────

    async def load_wall_history(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Load wall history from wall_history table.

        Returns DataFrame with:
            call_wall, put_wall, wall_strength, wall_range_pct,
            call_wall_migration, put_wall_migration, call_wall_persistence,
            put_wall_persistence, spot_vs_midpoint
        """
        if self.pool is None:
            return pd.DataFrame()

        query = """
            SELECT date, call_wall, put_wall, wall_strength, spot
            FROM wall_history
            WHERE symbol = $1
            {date_filter}
            ORDER BY date ASC
        """
        params = [symbol]
        date_filter = ""
        if start_date:
            params.append(start_date)
            date_filter += f" AND date >= ${len(params)}"
        if end_date:
            params.append(end_date)
            date_filter += f" AND date <= ${len(params)}"

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query.format(date_filter=date_filter), *params)

            if not rows:
                return pd.DataFrame()

            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)

            # Derived wall features
            spot = df.get("spot", df["call_wall"])  # fallback if spot not available
            df["wall_range"] = df["call_wall"] - df["put_wall"]
            df["wall_midpoint"] = (df["call_wall"] + df["put_wall"]) / 2
            df["wall_range_pct"] = df["wall_range"] / spot
            df["spot_vs_midpoint"] = (spot - df["wall_midpoint"]) / df[
                "wall_range"
            ].replace(0, np.nan)

            df["call_wall_migration"] = df["call_wall"].diff(1)
            df["put_wall_migration"] = df["put_wall"].diff(1)
            df["call_wall_migration5"] = df["call_wall"].diff(5)
            df["put_wall_migration5"] = df["put_wall"].diff(5)

            # Persistence: days at same strike (rolling count of no change)
            cw_same = (df["call_wall"].diff(1) == 0).astype(int)
            pw_same = (df["put_wall"].diff(1) == 0).astype(int)

            def _persistence(same: pd.Series) -> pd.Series:
                result = pd.Series(index=same.index, dtype=float)
                count = 0
                for idx, val in same.items():
                    count = count + 1 if val else 1
                    result[idx] = count
                return result

            df["call_wall_persistence"] = _persistence(cw_same)
            df["put_wall_persistence"] = _persistence(pw_same)

            # Stability (5-day std normalized by spot)
            df["call_wall_stability_5d"] = 1 - (
                df["call_wall"].rolling(5).std()
                / spot.rolling(5).mean().replace(0, np.nan)
            )
            df["put_wall_stability_5d"] = 1 - (
                df["put_wall"].rolling(5).std()
                / spot.rolling(5).mean().replace(0, np.nan)
            )

            logger.info(f"[DataLoader] Loaded {len(df)} wall rows for {symbol}")
            return df

        except Exception as e:
            logger.error(f"[DataLoader] Wall load failed: {e}")
            return pd.DataFrame()

    # ── IV / Options ──────────────────────────────────────────────────────────

    async def load_iv_daily(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Load daily IV metrics from warehouse_options_daily or options_chain_snapshots.

        Returns DataFrame with:
            atm_iv_ce, atm_iv_pe, iv_skew, iv_rank_252d, iv_percentile_252d,
            vrp_20d (IV - RV_20d)
        """
        if self.pool is None:
            return pd.DataFrame()

        # Try warehouse table first, fall back to options_history aggregate
        tables_to_try = [
            "warehouse_options_daily",
            "options_chain_snapshots",
        ]
        for table in tables_to_try:
            try:
                # Check table exists
                async with self.pool.acquire() as conn:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                        "WHERE table_name = $1);",
                        table,
                    )
                if exists:
                    return await self._load_iv_from_table(
                        table, symbol, start_date, end_date
                    )
            except Exception:
                continue

        # Fallback: aggregate from options_history
        return await self._load_iv_from_options_history(symbol, start_date, end_date)

    async def _load_iv_from_table(
        self, table: str, symbol: str, start_date: str | None, end_date: str | None
    ) -> pd.DataFrame:
        query = f"""
            SELECT date, atm_iv_ce, atm_iv_pe, iv_skew, iv_rank, iv_percentile
            FROM {table}
            WHERE symbol = $1
            ORDER BY date ASC
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, symbol)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)
            return self._enrich_iv(df)
        except Exception as e:
            logger.warning(f"[DataLoader] IV from {table} failed: {e}")
            return pd.DataFrame()

    async def _load_iv_from_options_history(
        self, symbol: str, start_date: str | None, end_date: str | None
    ) -> pd.DataFrame:
        """Aggregate ATM IV from raw options data."""
        query = """
            SELECT
                o.date,
                AVG(CASE WHEN o.option_type='CE' AND ABS(o.strike - s.spot) < 100 THEN o.iv END) AS atm_iv_ce,
                AVG(CASE WHEN o.option_type='PE' AND ABS(o.strike - s.spot) < 100 THEN o.iv END) AS atm_iv_pe,
                AVG(CASE WHEN o.option_type='PE' AND (o.strike - s.spot) BETWEEN -s.spot*0.06 AND -s.spot*0.04 THEN o.iv END)
                  - AVG(CASE WHEN o.option_type='CE' AND (o.strike - s.spot) BETWEEN s.spot*0.04 AND s.spot*0.06 THEN o.iv END)
                  AS iv_skew
            FROM options_history o
            JOIN (
                SELECT date, AVG(close) AS spot FROM ohlcv_history
                WHERE symbol = $1 AND interval = '1d'
                GROUP BY date
            ) s ON o.date = s.date
            WHERE o.symbol = $1
            GROUP BY o.date
            ORDER BY o.date ASC
        """
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, symbol)
            if not rows:
                return pd.DataFrame()
            df = pd.DataFrame(rows)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").astype(float)
            return self._enrich_iv(df)
        except Exception as e:
            logger.warning(f"[DataLoader] IV from options_history failed: {e}")
            return pd.DataFrame()

    def _enrich_iv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add IV rank, percentile, momentum, VRP to IV DataFrame."""
        if "atm_iv_ce" not in df.columns:
            return df

        df["atm_iv"] = (df["atm_iv_ce"].fillna(0) + df["atm_iv_pe"].fillna(0)) / 2
        atm = df["atm_iv"].replace(0, np.nan)

        # IV Rank (252d)
        def _iv_rank(x):
            if len(x) < 2:
                return np.nan
            mn, mx = x.min(), x.max()
            return (x.iloc[-1] - mn) / (mx - mn) if mx != mn else 0.5

        df["iv_rank_252d"] = atm.rolling(252).apply(_iv_rank, raw=False)
        df["iv_percentile_252d"] = atm.rolling(252).apply(
            lambda x: (x < x.iloc[-1]).sum() / len(x), raw=False
        )

        # IV momentum and acceleration
        df["iv_momentum_5d"] = atm.diff(5)
        df["iv_acceleration"] = atm.diff(1).diff(1)
        df["iv_zscore_60d"] = (atm - atm.rolling(60).mean()) / atm.rolling(
            60
        ).std().replace(0, np.nan)

        # Vol Risk Premium (IV - Realized Vol_20d)
        # Requires realized vol which we don't have here — placeholder
        df["vrp_placeholder"] = np.nan

        return df

    # ── FII/DII ───────────────────────────────────────────────────────────────

    async def load_fii_dii(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Load FII/DII data from fii_dii_data or fii_dii table.

        Returns DataFrame with:
            fii_net, dii_net, fii_net_cumulative_5d, fii_zscore_20d
        """
        if self.pool is None:
            return pd.DataFrame()

        tables = ["fii_dii_data", "fii_dii"]
        for table in tables:
            try:
                async with self.pool.acquire() as conn:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name=$1);",
                        table,
                    )
                if not exists:
                    continue
                query = f"""
                    SELECT date, fii_net, dii_net
                    FROM {table}
                    ORDER BY date ASC
                """
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(query)
                if not rows:
                    continue

                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").astype(float)

                df["fii_net_cumulative_5d"] = df["fii_net"].rolling(5).sum()
                df["dii_net_cumulative_5d"] = df["dii_net"].rolling(5).sum()
                roll = df["fii_net"].rolling(20)
                df["fii_zscore_20d"] = (
                    df["fii_net"] - roll.mean()
                ) / roll.std().replace(0, np.nan)
                df["fii_dii_battle"] = df["fii_net"] - df["dii_net"]

                logger.info(f"[DataLoader] Loaded {len(df)} FII/DII rows from {table}")
                return df

            except Exception as e:
                logger.warning(f"[DataLoader] FII/DII from {table} failed: {e}")
                continue

        return pd.DataFrame()

    # ── Composite Research Dataset ─────────────────────────────────────────────

    async def build_research_dataset(
        self,
        symbol: str = "NIFTY",
        interval: str = "1d",
        start_date: str | None = None,
        end_date: str | None = None,
        min_rows: int = 60,
    ) -> dict[str, pd.DataFrame]:
        """
        Load and align all research inputs into a single dictionary of DataFrames.
        All DataFrames share a common DatetimeIndex.

        Returns dict with keys:
            'ohlcv', 'oi', 'pcr', 'wall', 'iv', 'fii'
        and a merged 'features' DataFrame with all numeric features aligned.
        """
        logger.info(
            f"[DataLoader] Building research dataset for {symbol}/{interval}..."
        )

        # Load all sources concurrently
        ohlcv, oi_df, pcr_df, wall_df, iv_df, fii_df = await asyncio.gather(
            self.load_ohlcv(symbol, interval, start_date, end_date, min_rows),
            self.load_strike_oi_daily(symbol, start_date, end_date),
            self.load_pcr_history(symbol, start_date, end_date),
            self.load_wall_history(symbol, start_date, end_date),
            self.load_iv_daily(symbol, start_date, end_date),
            self.load_fii_dii(start_date, end_date),
            return_exceptions=False,
        )

        # Also compute OI entropy (separate query)
        try:
            oi_entropy = await self.load_oi_entropy_daily(symbol, start_date, end_date)
        except Exception:
            oi_entropy = pd.Series(dtype=float)

        datasets = {
            "ohlcv": ohlcv,
            "oi": oi_df,
            "pcr": pcr_df,
            "wall": wall_df,
            "iv": iv_df,
            "fii": fii_df,
        }

        # Merge all into features DataFrame aligned on date index
        features_parts = []
        target_cols = ["ret_1d", "ret_3d", "ret_5d", "ret_10d"]

        for name, df in datasets.items():
            if df is None or df.empty:
                logger.warning(f"[DataLoader] {name} is empty — skipping merge")
                continue
            # Drop forward return cols from non-ohlcv sources
            if name != "ohlcv":
                df = df.drop(
                    columns=[c for c in target_cols if c in df.columns], errors="ignore"
                )
            features_parts.append(df)

        if not oi_entropy.empty:
            features_parts.append(oi_entropy.to_frame("oi_entropy"))

        if features_parts:
            features = features_parts[0].copy()
            for df in features_parts[1:]:
                features = features.join(df, how="outer", rsuffix="_dup")
            # Drop duplicate columns
            dup_cols = [c for c in features.columns if c.endswith("_dup")]
            features = features.drop(columns=dup_cols)
            # Sort and forward-fill max 2 days
            features = features.sort_index().fillna(method="ffill", limit=2)
        else:
            features = pd.DataFrame()

        datasets["features"] = features

        n_features = (
            len([c for c in features.columns if c not in target_cols])
            if not features.empty
            else 0
        )
        logger.info(
            f"[DataLoader] Research dataset built: {len(features)} rows, "
            f"{n_features} feature columns, {symbol}"
        )
        return datasets

    async def list_available_tables(self) -> list[str]:
        """List all available tables in the database for research input discovery."""
        if self.pool is None:
            return []
        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' ORDER BY table_name;"
                )
            return [r["table_name"] for r in rows]
        except Exception as e:
            logger.error(f"[DataLoader] Table list failed: {e}")
            return []

    async def get_data_coverage(self, symbol: str = "NIFTY") -> dict[str, dict]:
        """Report data availability: date range and row count per source."""
        if self.pool is None:
            return {}

        sources = {
            "ohlcv": (
                "ohlcv_history",
                "timestamp::date",
                f"symbol='{symbol}' AND interval='1d'",
            ),
            "strike": ("strike_history", "date", f"symbol='{symbol}'"),
            "pcr": ("pcr_history", "date", f"symbol='{symbol}'"),
            "wall": ("wall_history", "date", f"symbol='{symbol}'"),
        }
        result = {}
        async with self.pool.acquire() as conn:
            for name, (table, date_col, where) in sources.items():
                try:
                    row = await conn.fetchrow(
                        f"SELECT COUNT(*) AS n, MIN({date_col}) AS first, MAX({date_col}) AS last "
                        f"FROM {table} WHERE {where};"
                    )
                    result[name] = {
                        "rows": int(row["n"]),
                        "first": str(row["first"]) if row["first"] else None,
                        "last": str(row["last"]) if row["last"] else None,
                    }
                except Exception as e:
                    result[name] = {"rows": 0, "error": str(e)}
        return result
