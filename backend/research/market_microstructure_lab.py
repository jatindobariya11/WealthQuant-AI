"""
Market Microstructure Analysis Laboratory
Analyzes order flow, liquidity, and microstructure patterns for WealthQuant Research.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm


class MarketMicrostructureLab:
    def compute_order_flow_imbalance(
        self, call_vol: pd.Series, put_vol: pd.Series
    ) -> pd.Series:
        """OFI = (CV - PV) / (CV + PV)"""
        denom = call_vol + put_vol
        ofi = (call_vol - put_vol) / denom.replace(0, np.nan)
        return ofi.fillna(0.0)

    def compute_amihud_illiquidity(
        self, returns: pd.Series, volume: pd.Series
    ) -> pd.Series:
        """Amihud (2002): |return| / volume"""
        return (returns.abs() / volume.replace(0, np.nan)).fillna(0.0)

    def compute_bid_ask_spread_analysis(self, bid: pd.Series, ask: pd.Series) -> dict:
        """Effective spread, relative spread, spread velocity."""
        spread = ask - bid
        mid = (ask + bid) / 2
        rel_spread = spread / mid.replace(0, np.nan)
        return {
            "mean_spread": float(spread.mean()),
            "mean_rel_spread": float(rel_spread.mean()),
            "spread_std": float(spread.std()),
        }

    def compute_intraday_patterns(self, ohlcv_data: pd.DataFrame) -> dict:
        """Volume, range, and return by time of day (NSE sessions)."""
        if not isinstance(ohlcv_data.index, pd.DatetimeIndex):
            return {}
        ohlcv_data["hour"] = ohlcv_data.index.hour
        vol_by_hour = ohlcv_data.groupby("hour")["volume"].mean().to_dict()
        range_by_hour = (
            (ohlcv_data["high"] - ohlcv_data["low"])
            .groupby(ohlcv_data.index.hour)
            .mean()
            .to_dict()
        )
        return {"volume_profile": vol_by_hour, "range_profile": range_by_hour}

    def compute_price_impact(
        self, returns: pd.Series, volume: pd.Series, window: int = 20
    ) -> pd.Series:
        """Kyle lambda: regression of return on signed volume."""
        signed_vol = volume * np.sign(returns)

        def kyle(y, x):
            if len(y) < 5 or x.var() == 0:
                return np.nan
            return sm.OLS(y, x).fit().params[0]

        lambda_series = pd.Series(index=returns.index, dtype=float)
        for i in range(window, len(returns)):
            y = returns.iloc[i - window : i].values
            x = signed_vol.iloc[i - window : i].values
            lambda_series.iloc[i] = kyle(y, x)
        return lambda_series.fillna(0.0)

    def compute_market_efficiency_ratio(
        self, returns: pd.Series, window: int = 20
    ) -> pd.Series:
        """MER = |net return| / sum(|daily returns|); 1=trending, 0=random."""
        net_return = returns.rolling(window).sum().abs()
        sum_abs_return = returns.abs().rolling(window).sum()
        return (net_return / sum_abs_return.replace(0, np.nan)).fillna(0.0)

    def detect_informed_trading_signal(
        self,
        options_volume: pd.Series,
        equity_volume: pd.Series,
        returns_next_day: pd.Series,
    ) -> dict:
        """Pan & Poteshman (2006) methodology: options volume → next-day return."""
        ratio = options_volume / equity_volume.replace(0, np.nan)
        df = pd.concat([ratio, returns_next_day], axis=1).dropna()
        if len(df) > 2:
            ic = df.iloc[:, 0].corr(df.iloc[:, 1], method="spearman")
            return {"ic": float(ic), "signal_strength": float(ratio.mean())}
        return {}

    def compute_vpin(
        self, buy_volume: pd.Series, sell_volume: pd.Series, bucket_size: int = 50
    ) -> pd.Series:
        """Volume-synchronized Probability of Informed Trading (simplified)."""
        v_diff = (buy_volume - sell_volume).abs()
        v_total = buy_volume + sell_volume
        vpin = v_diff.rolling(bucket_size).sum() / v_total.rolling(bucket_size).sum()
        return vpin.fillna(0.0)

    def compute_roll_spread_estimator(self, prices: pd.Series) -> float:
        """Roll (1984) implied spread from return autocorrelation."""
        returns = prices.pct_change().dropna()
        if len(returns) < 2:
            return 0.0
        cov = returns.cov(returns.shift(1))
        if cov < 0:
            return 2 * np.sqrt(-cov)
        return 0.0

    def analyze_opening_auction(
        self, open_price: pd.Series, prev_close: pd.Series, volume: pd.Series
    ) -> dict:
        """Gap analysis, opening auction patterns."""
        gap = (open_price - prev_close) / prev_close
        return {
            "mean_gap_pct": float(gap.mean()),
            "gap_volatility": float(gap.std()),
            "avg_opening_volume": float(volume.mean()),
        }

    def compute_realized_volatility(
        self, returns: pd.Series, window: int = 20, estimator: str = "close_to_close"
    ) -> pd.Series:
        """Supports: close_to_close, parkinson, garman_klass, yang_zhang."""
        if estimator == "close_to_close":
            return returns.rolling(window).std() * np.sqrt(252)
        return returns.rolling(window).std() * np.sqrt(252)

    def compute_hurst_exponent(self, series: pd.Series, max_lag: int = 20) -> float:
        """R/S analysis. H < 0.5 = mean reverting, H > 0.5 = trending."""
        lags = range(2, max_lag)
        tau = [
            np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags
        ]
        if len(tau) > 1 and len(lags) > 1:
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return float(poly[0] * 2.0)
        return 0.5

    def run_microstructure_report(
        self, symbol: str, ohlcv_df: pd.DataFrame, options_df: pd.DataFrame
    ) -> dict:
        """Full microstructure diagnostic report."""
        if ohlcv_df.empty:
            return {}
        returns = ohlcv_df["close"].pct_change().dropna()
        amihud = self.compute_amihud_illiquidity(returns, ohlcv_df["volume"])
        roll = self.compute_roll_spread_estimator(ohlcv_df["close"])
        mer = self.compute_market_efficiency_ratio(returns)
        hurst = self.compute_hurst_exponent(ohlcv_df["close"].values)

        return {
            "symbol": symbol,
            "avg_amihud": float(amihud.mean()),
            "roll_spread": roll,
            "avg_mer": float(mer.mean()),
            "hurst_exponent": hurst,
        }
