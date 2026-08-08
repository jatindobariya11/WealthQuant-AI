"""
WealthQuant Backtesting Engine.
Simulates event-driven historical execution, incorporates Indian transaction costs,
and tracks portfolio metrics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd

from core.shared_features import (
    compute_adx,
    compute_atr,
    compute_bollinger_bands,
    compute_rsi,
    compute_volume_ratio,
)
from pipeline.base import MarketSnapshot, TickEvent
from pipeline.institutional_engine import Stage5_5Institutional
from pipeline.stage2_hawkes import Stage2Hawkes
from pipeline.stage3_kalman import Stage3Kalman
from pipeline.stage4_particle import Stage4Particle
from pipeline.stage5_regime import Stage5Regime
from pipeline.stage6_ensemble import Stage6Ensemble
from pipeline.stage7_meta_learning import Stage7MetaLearning
from pipeline.stage8_bayesian_fusion import Stage8BayesianFusion
from pipeline.stage9_probability_engine import Stage9ProbabilityEngine

logger = logging.getLogger("pipeline.backtest")


def calculate_indian_transaction_cost(
    price: float, qty: int, side: str, order_type: str = "INTRADAY"
) -> float:
    """
    Computes complete transaction charges for Indian stock markets.
    Includes Brokerage, STT, Exchange transaction charges, GST, SEBI fee, and Stamp duty.
    """
    trade_value = price * qty
    if trade_value <= 0:
        return 0.0

    # 1. Brokerage: Flat 20 INR or 0.05% of trade value, whichever is lower
    brokerage = min(20.0, 0.0005 * trade_value)

    # 2. Exchange Transaction Charges: 0.00343% (NSE Equity transaction charges)
    exc_charges = 0.0000343 * trade_value

    # 3. GST: 18% of (Brokerage + Exchange Charges)
    gst = 0.18 * (brokerage + exc_charges)

    # 4. SEBI turnover fee: 0.0001% (10 INR per crore)
    sebi_fee = 0.000001 * trade_value

    # 5. STT (Securities Transaction Tax) & Stamp Duty based on trade type
    stt = 0.0
    stamp_duty = 0.0

    if order_type.upper() == "INTRADAY":
        # STT: 0.025% on Sell side only
        if side.upper() == "SELL":
            stt = 0.00025 * trade_value
        # Stamp Duty: 0.003% on Buy side only
        if side.upper() == "BUY":
            stamp_duty = 0.00003 * trade_value
    else:  # DELIVERY
        # STT: 0.1% on both Buy and Sell sides
        stt = 0.001 * trade_value
        # Stamp Duty: 0.015% on Buy side only
        if side.upper() == "BUY":
            stamp_duty = 0.00015 * trade_value

    total_cost = brokerage + exc_charges + gst + sebi_fee + stt + stamp_duty
    return round(total_cost, 2)


@dataclass
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime | None = None
    side: str = "BUY"  # BUY or SELL
    entry_price: float = 0.0
    exit_price: float | None = None
    qty: int = 0
    kelly_fraction: float = 0.0
    transaction_cost: float = 0.0
    returns: float = 0.0
    realized_pnl: float = 0.0


class BacktestEngine:
    def __init__(
        self,
        initial_capital: float = 10000000.0,
        order_type: str = "INTRADAY",
        kelly_cap: float = 0.10,
    ):

        self.initial_capital = initial_capital
        self.order_type = order_type
        self.kelly_cap = kelly_cap

        # Instantiate pipeline stages
        self.stage2 = Stage2Hawkes()
        self.stage3 = Stage3Kalman()
        self.stage4 = Stage4Particle()
        self.stage5 = Stage5Regime()
        self.stage5_5 = Stage5_5Institutional()
        self.stage6 = Stage6Ensemble()
        self.stage7 = Stage7MetaLearning()
        self.stage8 = Stage8BayesianFusion()
        self.stage9 = Stage9ProbabilityEngine()

    def precompute_indicators(self, df: pd.DataFrame) -> dict:
        """
        Precomputes technical indicators for the entire historical dataframe
        using the shared standardized formulas.
        """
        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        rsi = compute_rsi(close).fillna(50.0)
        adx = compute_adx(high, low, close).fillna(20.0)
        vol_ratio = compute_volume_ratio(volume).fillna(1.0)
        bb_upper, bb_mid, bb_lower = compute_bollinger_bands(close)
        bb_upper = bb_upper.fillna(close * 1.02)
        bb_mid = bb_mid.fillna(close)
        bb_lower = bb_lower.fillna(close * 0.98)
        atr = compute_atr(high, low, close).fillna(close * 0.01)

        return {
            "rsi": rsi,
            "adx": adx,
            "vol_ratio": vol_ratio,
            "bb_upper": bb_upper,
            "bb_mid": bb_mid,
            "bb_lower": bb_lower,
            "atr": atr,
        }

    def precompute_tick_events(self, df: pd.DataFrame):
        """Precompute all tick events for the entire historical dataframe to optimize execution speed."""
        close = df["close"]
        open_p = df["open"]
        volume = df["volume"]

        log_returns = np.log(close / close.shift(1)).fillna(0.0)
        ret_std = log_returns.rolling(20).std().fillna(0.01)
        vol_median = volume.rolling(20).median().fillna(1.0)

        precomputed = []
        for i in range(len(df)):
            dt = df.index[i]
            ts = dt.timestamp() if hasattr(dt, "timestamp") else float(i)
            events = []

            # Price jump check (>2 sigma)
            ret = log_returns.iloc[i]
            std = ret_std.iloc[i]
            if std > 1e-6 and abs(ret) > 2.0 * std:
                events.append(
                    TickEvent(
                        timestamp=ts,
                        event_type="price_jump",
                        magnitude=float(abs(ret)),
                        direction=1 if ret > 0 else -1,
                        metadata={"price": float(close.iloc[i]), "return": float(ret)},
                    )
                )

            # Volume spike check (>3x median)
            vol = volume.iloc[i]
            med_vol = vol_median.iloc[i]
            if vol > 3.0 * med_vol and vol > 100:
                events.append(
                    TickEvent(
                        timestamp=ts,
                        event_type="volume_spike",
                        magnitude=float(vol / (med_vol if med_vol > 0 else 1.0)),
                        direction=1 if close.iloc[i] >= open_p.iloc[i] else -1,
                        metadata={
                            "volume": float(vol),
                            "median_volume": float(med_vol),
                        },
                    )
                )
            precomputed.append(events)

        return precomputed

    def extract_tick_events(self, df: pd.DataFrame, idx: int) -> list:
        """
        Extract recent tick events for the Hawkes process up to the current index.
        """
        if not hasattr(self, "precomputed_events"):
            self.precomputed_events = self.precompute_tick_events(df)

        events = []
        start_idx = max(0, idx - 100)
        for i in range(start_idx, idx + 1):
            events.extend(self.precomputed_events[i])
        events.sort(key=lambda x: x.timestamp)
        return events

    async def run_backtest(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str = "15m",
        warmup_bars: int = 60,
        progress_cb=None,
    ) -> dict:
        """
        Runs the backtest loop over the historical dataframe.
        """
        df = df.sort_index()
        n_bars = len(df)
        if n_bars <= warmup_bars:
            raise ValueError(
                f"Insufficient historical data ({n_bars} <= {warmup_bars}) for backtesting."
            )

        logger.info(f"Starting historical backtest for {symbol} on {n_bars} bars.")

        # Precompute indicators
        indicators = self.precompute_indicators(df)

        # Portfolio State
        cash = self.initial_capital
        equity_curve = []
        trades = []
        active_trade = None
        bars_held = 0

        # Results metrics arrays
        forecast_signals = []
        expected_returns = []
        actual_prices = []
        timestamps = []
        institutional_history = []
        forecast_probs = []
        regimes_history = []

        for i in range(warmup_bars, n_bars):
            t = df.index[i]
            price = float(df["close"].iloc[i])
            actual_prices.append(price)
            timestamps.append(t)

            # Construct historical slice (no lookahead!)
            slice_df = df.iloc[: i + 1]

            # Create indicators dict for this snapshot
            snap_indicators = {
                "rsi": float(indicators["rsi"].iloc[i]),
                "adx": float(indicators["adx"].iloc[i]),
                "volume_ratio": float(indicators["vol_ratio"].iloc[i]),
                "bb_upper": float(indicators["bb_upper"].iloc[i]),
                "bb_mid": float(indicators["bb_mid"].iloc[i]),
                "bb_lower": float(indicators["bb_lower"].iloc[i]),
                "atr": float(indicators["atr"].iloc[i]),
            }

            # Extract tick events
            tick_events = self.extract_tick_events(df, i)

            # Construct MarketSnapshot
            snapshot = MarketSnapshot(
                symbol=symbol.upper(),
                timestamp=t,
                interval=timeframe,
                ohlcv=slice_df,
                tick_events=tick_events,
                indicators=snap_indicators,
                options={"pcr": 1.0, "oi_score": 0.0, "atm_iv": 0.15},
                global_context={"vix": 15.0},
                news_sentiment={"score": 0.0, "label": "NEUTRAL"},
            )

            # Execute pipeline stages (bypassing slow API adapters)
            try:
                hawkes = self.stage2.process(snapshot)
                kalman = self.stage3.process(snapshot)
                particle = self.stage4.process(snapshot)
                regime = self.stage5.process(snapshot, kalman, particle)
                institutional = self.stage5_5.process(snapshot, regime)
                institutional_history.append(institutional)
                ensemble = self.stage6.process(
                    snapshot, hawkes, kalman, particle, regime
                )
                meta_learning = self.stage7.process(
                    ensemble, regime, symbol=symbol.upper()
                )
                fusion = self.stage8.process(
                    price,
                    hawkes,
                    kalman,
                    particle,
                    meta_learning,
                    regime,
                    institutional,
                )
                probabilities = self.stage9.process(symbol.upper(), fusion, regime)
            except Exception as e:
                logger.error(f"Pipeline failed at bar {i} ({t}): {e}", exc_info=True)
                # Append current portfolio equity
                portfolio_value = cash + (
                    active_trade.qty * price if active_trade else 0.0
                )
                equity_curve.append(portfolio_value)
                continue

            sig = probabilities.signal
            kelly_f = probabilities.kelly_fraction
            forecast_signals.append(sig)
            expected_returns.append(probabilities.expected_return)
            forecast_probs.append(
                {
                    "p_up": probabilities.p_up,
                    "p_down": probabilities.p_down,
                    "p_sideways": probabilities.p_sideways,
                }
            )
            regimes_history.append(regime.current_regime)

            # ─── Portfolio Execution Simulation ───
            # Update active trade holding duration
            if active_trade:
                bars_held += 1

                # Check for Exit Condition: Horizon limit (5 bars) or reverse strong signal
                should_exit = False
                if bars_held >= 5:
                    should_exit = True
                elif active_trade.side == "BUY" and sig in ["SELL", "STRONG_SELL"]:
                    should_exit = True
                elif active_trade.side == "SELL" and sig in ["BUY", "STRONG_BUY"]:
                    should_exit = True

                if should_exit:
                    # Execute Close order
                    exit_price = price
                    active_trade.exit_time = t
                    active_trade.exit_price = exit_price

                    # Transaction costs on close
                    close_cost = calculate_indian_transaction_cost(
                        exit_price,
                        active_trade.qty,
                        "SELL" if active_trade.side == "BUY" else "BUY",
                        self.order_type,
                    )
                    active_trade.transaction_cost += close_cost

                    # Calculate PnL
                    dir_mult = 1.0 if active_trade.side == "BUY" else -1.0
                    pnl_raw = (
                        (exit_price - active_trade.entry_price)
                        * active_trade.qty
                        * dir_mult
                    )
                    active_trade.realized_pnl = pnl_raw - active_trade.transaction_cost
                    active_trade.returns = (
                        active_trade.realized_pnl
                        / (active_trade.entry_price * active_trade.qty)
                        if active_trade.qty > 0
                        else 0.0
                    )

                    cash += (
                        (active_trade.entry_price * active_trade.qty * dir_mult)
                        + pnl_raw
                        - active_trade.transaction_cost
                    )
                    trades.append(active_trade)
                    active_trade = None
                    bars_held = 0

            # Check for Entry Condition: No active position and clean signal
            if not active_trade and sig in ["BUY", "STRONG_BUY", "SELL", "STRONG_SELL"]:
                # Position Sizing: Capped Kelly size (Max 10% allocation)
                alloc_fraction = min(max(0.0, kelly_f), self.kelly_cap)
                if alloc_fraction > 0.001:
                    trade_allocation = cash * alloc_fraction
                    qty = int(trade_allocation / price)

                    if qty > 0:
                        side = "BUY" if sig in ["BUY", "STRONG_BUY"] else "SELL"
                        entry_cost = calculate_indian_transaction_cost(
                            price, qty, side, self.order_type
                        )

                        active_trade = Trade(
                            symbol=symbol.upper(),
                            entry_time=t,
                            side=side,
                            entry_price=price,
                            qty=qty,
                            kelly_fraction=alloc_fraction,
                            transaction_cost=entry_cost,
                        )
                        bars_held = 0
                        # Dedicate entry cash allocation
                        dir_mult = 1.0 if side == "BUY" else -1.0
                        cash -= (price * qty * dir_mult) + entry_cost

            # Calculate current portfolio net asset value (NAV)
            portfolio_value = cash
            if active_trade:
                dir_mult = 1.0 if active_trade.side == "BUY" else -1.0
                portfolio_value += (
                    active_trade.entry_price * active_trade.qty * dir_mult
                ) + ((price - active_trade.entry_price) * active_trade.qty * dir_mult)
            equity_curve.append(portfolio_value)

            if progress_cb and i % 50 == 0:
                progress_cb(i / n_bars)

        # ─── Calculate Summary Performance Metrics ───
        equity_series = pd.Series(equity_curve)
        equity_returns = equity_series.pct_change().fillna(0.0)

        total_return = float(
            (equity_curve[-1] - self.initial_capital) / self.initial_capital
        )

        # Annualization factor (assuming 15m bars, 25 bars per day, 250 days = 6250 bars/yr)
        if timeframe == "1d":
            annual_factor = 252.0
        elif timeframe == "1h":
            annual_factor = 252.0 * 6.25
        else:  # 15m
            annual_factor = 252.0 * 25.0

        ann_return = (
            float((1.0 + total_return) ** (annual_factor / len(equity_curve)) - 1.0)
            if len(equity_curve) > 0
            else 0.0
        )
        ann_vol = float(equity_returns.std() * np.sqrt(annual_factor))

        sharpe = float(ann_return / ann_vol) if ann_vol > 0 else 0.0

        # Sortino Ratio
        downside_returns = equity_returns[equity_returns < 0]
        downside_std = downside_returns.std() * np.sqrt(annual_factor)
        sortino = float(ann_return / downside_std) if downside_std > 0 else 0.0

        # Max Drawdown
        peaks = equity_series.cummax()
        drawdowns = (peaks - equity_series) / peaks
        max_dd = float(drawdowns.max())

        # Trade Stats
        total_trades = len(trades)
        wins = sum(1 for t in trades if t.realized_pnl > 0)
        win_rate = float(wins / total_trades) if total_trades > 0 else 0.0

        gross_profit = sum(t.realized_pnl for t in trades if t.realized_pnl > 0)
        gross_loss = abs(sum(t.realized_pnl for t in trades if t.realized_pnl < 0))
        profit_factor = (
            float(gross_profit / gross_loss)
            if gross_loss > 0
            else (float("inf") if gross_profit > 0 else 1.0)
        )

        results_list = [
            {
                "timestamp": t.isoformat() if hasattr(t, "isoformat") else str(t),
                "price": p,
                "signal": s,
                "expected_return": er,
                "equity": eq,
                "probabilities": probs,
                "regime": reg,
            }
            for t, p, s, er, eq, probs, reg in zip(
                timestamps,
                actual_prices,
                forecast_signals,
                expected_returns,
                equity_curve,
                forecast_probs,
                regimes_history,
            )
        ]

        trade_logs = [
            {
                "symbol": t.symbol,
                "side": t.side,
                "qty": t.qty,
                "entry_time": t.entry_time.isoformat()
                if hasattr(t.entry_time, "isoformat")
                else str(t.entry_time),
                "entry_price": t.entry_price,
                "exit_time": t.exit_time.isoformat()
                if t.exit_time and hasattr(t.exit_time, "isoformat")
                else str(t.exit_time),
                "exit_price": t.exit_price,
                "realized_pnl": t.realized_pnl,
                "returns": t.returns,
                "transaction_cost": t.transaction_cost,
            }
            for t in trades
        ]

        return {
            "name": f"Backtest_{symbol}_{timeframe}",
            "description": f"Ensemble backtest using Kelly cap {self.kelly_cap * 100}%",
            "strategy_config": {
                "kelly_cap": self.kelly_cap,
                "order_type": self.order_type,
                "timeframe": timeframe,
            },
            "symbols": [symbol.upper()],
            "start_date": df.index[warmup_bars].to_pydatetime()
            if hasattr(df.index[warmup_bars], "to_pydatetime")
            else datetime.now(),
            "end_date": df.index[-1].to_pydatetime()
            if hasattr(df.index[-1], "to_pydatetime")
            else datetime.now(),
            "total_return": total_return,
            "annualized_return": ann_return,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "results": {"signals": results_list, "trades": trade_logs},
            "equity_curve": {
                "timestamps": [
                    t.isoformat() if hasattr(t, "isoformat") else str(t)
                    for t in timestamps
                ],
                "values": equity_curve,
            },
            "institutional_history": institutional_history,
        }
