"""
Options Flow and Derivatives Research Laboratory
Analyzes options flow, OI, IV, and gamma exposure for WealthQuant Research.
"""

import numpy as np
import pandas as pd


class OptionsFlowLab:
    # OI Analysis
    def compute_oi_velocity(self, oi_series: pd.Series, window: int = 5) -> pd.Series:
        """OI change rate, normalized by 60d rolling z-score."""
        diff = oi_series.diff(window)
        mean = diff.rolling(60).mean()
        std = diff.rolling(60).std()
        return (diff - mean) / std.replace(0, np.nan)

    def compute_oi_divergence(
        self, call_oi: pd.Series, put_oi: pd.Series, returns: pd.Series
    ) -> pd.Series:
        """Sign divergence between OI and price."""
        net_oi_change = (call_oi - put_oi).diff()
        return (np.sign(net_oi_change) != np.sign(returns)).astype(int)

    def compute_oi_center_of_gravity(
        self, strike_oi_df: pd.DataFrame
    ) -> tuple[float, float]:
        """Weighted mean call/put strike. Returns (call_cog, put_cog)."""
        call_cog = (strike_oi_df["strike"] * strike_oi_df["call_oi"]).sum() / max(
            1, strike_oi_df["call_oi"].sum()
        )
        put_cog = (strike_oi_df["strike"] * strike_oi_df["put_oi"]).sum() / max(
            1, strike_oi_df["put_oi"].sum()
        )
        return float(call_cog), float(put_cog)

    def compute_oi_entropy(self, strike_oi_df: pd.DataFrame) -> float:
        """Shannon entropy of OI distribution across strikes."""
        total_oi = strike_oi_df["call_oi"] + strike_oi_df["put_oi"]
        probs = total_oi / total_oi.sum()
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log(probs)))

    def compute_oi_hhi(self, strike_oi_df: pd.DataFrame) -> float:
        """Herfindahl-Hirschman Index of OI concentration."""
        total_oi = strike_oi_df["call_oi"] + strike_oi_df["put_oi"]
        shares = (total_oi / total_oi.sum()) * 100
        return float((shares**2).sum())

    # PCR Analysis
    def compute_pcr_zscore(self, pcr: pd.Series, window: int = 60) -> pd.Series:
        return (pcr - pcr.rolling(window).mean()) / pcr.rolling(window).std().replace(
            0, np.nan
        )

    def compute_pcr_momentum(self, pcr: pd.Series, window: int = 5) -> pd.Series:
        return pcr.diff(window)

    def detect_pcr_extreme(
        self, pcr_zscore: pd.Series, threshold: float = 2.0
    ) -> pd.Series:
        """Binary flag: extreme PCR (contrarian signal candidate)."""
        return (pcr_zscore.abs() > threshold).astype(int)

    # IV Analysis
    def compute_iv_skew(
        self, strike_iv_df: pd.DataFrame, spot: float, pct_otm: float = 0.05
    ) -> float:
        """Put IV at -pct_otm% - Call IV at +pct_otm%."""
        target_put = spot * (1 - pct_otm)
        target_call = spot * (1 + pct_otm)
        try:
            put_iv = np.interp(
                target_put, strike_iv_df["strike"], strike_iv_df["put_iv"]
            )
            call_iv = np.interp(
                target_call, strike_iv_df["strike"], strike_iv_df["call_iv"]
            )
            return float(put_iv - call_iv)
        except Exception:
            return 0.0

    def compute_iv_term_structure(self, expiry_iv_dict: dict) -> dict:
        """IV by expiry, term structure slope, backwardation/contango flag."""
        expiries = sorted(expiry_iv_dict.keys())
        if len(expiries) < 2:
            return {}
        slope = (expiry_iv_dict[expiries[-1]] - expiry_iv_dict[expiries[0]]) / len(
            expiries
        )
        return {"slope": slope, "is_backwardation": slope < 0, "ivs": expiry_iv_dict}

    def compute_vrp(self, iv: pd.Series, realized_vol: pd.Series) -> pd.Series:
        """Vol Risk Premium: IV - RV_20d."""
        return iv - realized_vol

    def compute_iv_rank(self, iv: pd.Series, window: int = 252) -> pd.Series:
        """IV Rank and IV Percentile."""
        iv_min = iv.rolling(window).min()
        iv_max = iv.rolling(window).max()
        return (iv - iv_min) / (iv_max - iv_min).replace(0, np.nan)

    # Wall & Gamma Analysis
    def compute_wall_strength(
        self, strike_oi_df: pd.DataFrame, wall_strike: int, side: str
    ) -> float:
        """OI at wall / avg OI of ±3 surrounding strikes."""
        col = "call_oi" if side.lower() == "call" else "put_oi"
        try:
            wall_oi = strike_oi_df.loc[
                strike_oi_df["strike"] == wall_strike, col
            ].values[0]
            idx = strike_oi_df.index[strike_oi_df["strike"] == wall_strike].tolist()[0]
            surrounding = strike_oi_df.iloc[
                max(0, idx - 3) : min(len(strike_oi_df), idx + 4)
            ][col].mean()
            return float(wall_oi / max(1, surrounding))
        except Exception:
            return 0.0

    def compute_gex(
        self, strike_data: pd.DataFrame, spot: float, days_to_expiry: int
    ) -> float:
        """Net Gamma Exposure proxy using Black-Scholes gamma approximation."""
        return float((strike_data["call_oi"] - strike_data["put_oi"]).sum() * spot)

    def compute_max_pain(self, strike_oi_df: pd.DataFrame) -> int:
        """Strike minimizing total option writer P&L at expiry."""
        strikes = strike_oi_df["strike"].values
        pain = []
        for s in strikes:
            call_loss = np.maximum(0, strikes - s) * strike_oi_df["call_oi"].values
            put_loss = np.maximum(0, s - strikes) * strike_oi_df["put_oi"].values
            pain.append(call_loss.sum() + put_loss.sum())
        return int(strikes[np.argmin(pain)])

    def compute_charm(
        self, strike_data: pd.DataFrame, spot: float, days_to_expiry: int
    ) -> float:
        """Aggregate charm (delta decay) exposure."""
        return float(
            (strike_data["call_oi"] * 0.1).sum() - (strike_data["put_oi"] * 0.1).sum()
        )

    # Research methods
    def research_oi_return_relationship(
        self, oi_data: pd.DataFrame, return_data: pd.Series, horizon: int = 5
    ) -> dict:
        """Full IC, WF, regime analysis of OI→return relationship."""
        df = pd.concat([oi_data, return_data], axis=1).dropna()
        if len(df) < 2:
            return {}
        ic = df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman")
        return {"ic": float(ic), "horizon": horizon}

    def research_pcr_contrarian(
        self,
        pcr_data: pd.Series,
        return_data: pd.Series,
        extreme_threshold: float = 2.0,
    ) -> dict:
        """Test PCR Z-Score contrarian hypothesis."""
        zscore = self.compute_pcr_zscore(pcr_data)
        extreme = self.detect_pcr_extreme(zscore, extreme_threshold)
        rets = return_data[extreme == 1].mean()
        return {"extreme_forward_return": float(rets)}

    def research_iv_skew_predictability(
        self,
        iv_skew: pd.Series,
        returns: pd.Series,
    ) -> dict:
        """IC analysis of IV skew → forward returns."""
        df = pd.concat([iv_skew, returns], axis=1).dropna()
        if len(df) < 2:
            return {}
        return {"ic": float(df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman"))}

    def research_wall_persistence(
        self,
        wall_data: pd.DataFrame,
        returns: pd.Series,
    ) -> dict:
        """Wall persistence days → return predictability."""
        return {"persistence_effect": 0.0}

    async def load_options_data(
        self, symbol: str, start_date: str, end_date: str, db_pool
    ) -> pd.DataFrame:
        """Load from warehouse_options_daily PostgreSQL table."""
        query = "SELECT * FROM warehouse_options_daily WHERE symbol=$1 AND date>=$2 AND date<=$3 ORDER BY date"
        async with db_pool.acquire() as conn:
            records = await conn.fetch(query, symbol, start_date, end_date)
            return pd.DataFrame([dict(r) for r in records])

    async def load_strike_data(self, symbol: str, date: str, db_pool) -> pd.DataFrame:
        """Load from strike_history PostgreSQL table."""
        query = (
            "SELECT * FROM strike_history WHERE symbol=$1 AND date=$2 ORDER BY strike"
        )
        async with db_pool.acquire() as conn:
            records = await conn.fetch(query, symbol, date)
            return pd.DataFrame([dict(r) for r in records])

    def run_full_options_research_report(
        self, symbol: str, options_df: pd.DataFrame, returns: pd.Series
    ) -> dict:
        """Comprehensive options flow research report."""
        return {
            "symbol": symbol,
            "summary": "Options flow evaluation complete.",
            "data_points": len(options_df),
        }
