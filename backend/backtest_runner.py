"""
WealthQuant Backtesting Engine — Trade Simulation Runner
=========================================================
Executes bar-by-bar trade simulation using stored predictions from PostgreSQL.
Tracks: MFE, MAE, target/stop hits, holding time, regime context, options context.

Two modes:
    stored  — use signals from predictions table (fast)
    replay  — re-run full 10-stage pipeline on OHLCV history (accurate)
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from core.shared_features import compute_atr
from pipeline.backtest_engine import calculate_indian_transaction_cost

logger = logging.getLogger("backtest.runner")

SIGNAL_BUY = {"BUY", "STRONG_BUY"}
SIGNAL_SELL = {"SELL", "STRONG_SELL"}
SIGNAL_ALL = SIGNAL_BUY | SIGNAL_SELL


@dataclass
class EnrichedTrade:
    """Extended trade record with full analytics."""

    symbol: str
    side: str  # BUY or SELL
    entry_time: datetime = None
    exit_time: datetime = None
    entry_price: float = 0.0
    exit_price: float = 0.0
    target_price: float = 0.0
    stop_price: float = 0.0
    qty: int = 0
    kelly_fraction: float = 0.0
    transaction_cost: float = 0.0
    realized_pnl: float = 0.0
    returns: float = 0.0
    holding_bars: int = 0
    exit_reason: str = ""  # TARGET | STOP | TIME_EXIT | SIGNAL_REVERSAL
    # MFE / MAE
    mfe: float = 0.0  # Maximum Favorable Excursion (points)
    mae: float = 0.0  # Maximum Adverse Excursion (points)
    mfe_pct: float = 0.0
    mae_pct: float = 0.0
    # Context at entry
    signal: str = ""
    signal_confidence: float = 0.0
    regime_at_entry: str = ""
    expected_return: float = 0.0
    p_up: float = 0.0
    p_down: float = 0.0
    # Options context
    pcr_at_entry: float = 0.0
    call_wall_at_entry: float = 0.0
    put_wall_at_entry: float = 0.0
    atm_iv_at_entry: float = 0.0
    gamma_pressure_at_entry: float = 0.0
    # FII/DII at entry
    fii_net_at_entry: float = 0.0
    dii_net_at_entry: float = 0.0
    # Prediction accuracy
    direction_correct: bool = False
    target_hit: bool = False
    stop_hit: bool = False


class BacktestRunner:
    """
    Bar-by-bar trade simulation runner.

    Uses stored predictions from PostgreSQL as signal source (mode='stored').
    Supports Kelly position sizing, Indian transaction costs, and enriched
    trade tracking (MFE, MAE, target/stop, regime context, options context).
    """

    def __init__(
        self,
        initial_capital: float = 10_000_000.0,
        order_type: str = "INTRADAY",
        kelly_cap: float = 0.10,
        target_atr_mult: float = 2.0,
        stop_atr_mult: float = 1.0,
        time_exit_bars: int = 5,
    ):
        self.initial_capital = initial_capital
        self.order_type = order_type
        self.kelly_cap = kelly_cap
        self.target_atr_mult = target_atr_mult
        self.stop_atr_mult = stop_atr_mult
        self.time_exit_bars = time_exit_bars

    def _get_prediction_at(
        self, predictions: pd.DataFrame, ts: pd.Timestamp
    ) -> dict | None:
        """Get stored prediction for exact timestamp, or nearest prior bar."""
        if predictions.empty:
            return None
        # Exact match
        if ts in predictions.index:
            row = predictions.loc[ts]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return row.to_dict()
        # Nearest prior prediction within 1 bar (15m)
        prior = predictions.index[predictions.index <= ts]
        if len(prior) == 0:
            return None
        nearest = prior[-1]
        delta = ts - nearest
        if delta.total_seconds() <= 15 * 60:  # within 1 bar
            row = predictions.loc[nearest]
            if isinstance(row, pd.DataFrame):
                row = row.iloc[0]
            return row.to_dict()
        return None

    def _get_options_at(self, options: pd.DataFrame, ts: pd.Timestamp) -> dict:
        """Get options context at timestamp (forward-filled, so no lookahead)."""
        if options.empty or len(options) == 0:
            return {}
        if ts in options.index:
            row = options.loc[ts]
        else:
            prior = options.index[options.index <= ts]
            if len(prior) == 0:
                return {}
            row = options.loc[prior[-1]]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        return {
            k: (float(v) if v is not None else 0.0)
            for k, v in row.items()
            if isinstance(v, (int, float)) or v is None
        }

    def _get_fii_at(self, fii_aligned: pd.DataFrame, ts: pd.Timestamp) -> dict:
        """Get FII/DII at timestamp."""
        if fii_aligned.empty:
            return {"fii_net": 0.0, "dii_net": 0.0}
        if ts in fii_aligned.index:
            row = fii_aligned.loc[ts]
            return {
                "fii_net": float(row.get("fii_net", 0.0)),
                "dii_net": float(row.get("dii_net", 0.0)),
            }
        return {"fii_net": 0.0, "dii_net": 0.0}

    async def run_stored_backtest(self, bundle: dict) -> dict:
        """
        Run backtest using STORED predictions from PostgreSQL.
        Fast path — signals come directly from the predictions table.

        No lookahead guarantee: at each bar i, only predictions with
        timestamp <= ohlcv.index[i] are consulted.
        """
        symbol = bundle["symbol"]
        timeframe = bundle["timeframe"]
        ohlcv = bundle["ohlcv"]
        preds = bundle["predictions"]
        regime_labels = bundle["regime_labels"]
        options = bundle["options"]
        fii_df = bundle["fii_dii"]

        if ohlcv.empty:
            raise ValueError(f"Empty OHLCV for {symbol}/{timeframe}")

        # Precompute ATR for position sizing
        atr_series = compute_atr(ohlcv["high"], ohlcv["low"], ohlcv["close"]).fillna(
            ohlcv["close"] * 0.005
        )

        n = len(ohlcv)
        warmup = min(60, n // 4)

        cash = self.initial_capital
        equity_curve = []
        all_trades: list[EnrichedTrade] = []
        active_trade: EnrichedTrade | None = None
        bars_held = 0

        per_bar_equity = []

        logger.info(
            f"[Runner] Starting stored backtest: {symbol}/{timeframe}, "
            f"{n} bars, warmup={warmup}"
        )

        for i in range(warmup, n):
            ts = ohlcv.index[i]
            price = float(ohlcv["close"].iloc[i])
            high = float(ohlcv["high"].iloc[i])
            low = float(ohlcv["low"].iloc[i])
            atr = float(atr_series.iloc[i])

            # ── Manage active trade ────────────────────────────────
            if active_trade is not None:
                bars_held += 1
                dir_mult = 1.0 if active_trade.side == "BUY" else -1.0

                # Update MFE / MAE intra-bar
                favorable = (
                    (high - active_trade.entry_price)
                    if active_trade.side == "BUY"
                    else (active_trade.entry_price - low)
                )
                adverse = (
                    (active_trade.entry_price - low)
                    if active_trade.side == "BUY"
                    else (high - active_trade.entry_price)
                )
                active_trade.mfe = max(active_trade.mfe, favorable)
                active_trade.mae = max(active_trade.mae, adverse)

                # Check target hit
                target_hit = (
                    high >= active_trade.target_price and active_trade.side == "BUY"
                ) or (low <= active_trade.target_price and active_trade.side == "SELL")
                # Check stop hit
                stop_hit = (
                    low <= active_trade.stop_price and active_trade.side == "BUY"
                ) or (high >= active_trade.stop_price and active_trade.side == "SELL")
                # Check signal reversal (get prediction at this bar)
                current_pred = self._get_prediction_at(preds, ts)
                current_sig = current_pred["signal"] if current_pred else "NEUTRAL"
                reversal = (
                    active_trade.side == "BUY" and current_sig in SIGNAL_SELL
                ) or (active_trade.side == "SELL" and current_sig in SIGNAL_BUY)

                should_exit = False
                exit_reason = ""

                if target_hit:
                    should_exit = True
                    exit_reason = "TARGET"
                    active_trade.target_hit = True
                    exit_price = active_trade.target_price
                elif stop_hit:
                    should_exit = True
                    exit_reason = "STOP"
                    active_trade.stop_hit = True
                    exit_price = active_trade.stop_price
                elif bars_held >= self.time_exit_bars:
                    should_exit = True
                    exit_reason = "TIME_EXIT"
                    exit_price = price
                elif reversal:
                    should_exit = True
                    exit_reason = "SIGNAL_REVERSAL"
                    exit_price = price

                if should_exit:
                    close_cost = calculate_indian_transaction_cost(
                        exit_price,
                        active_trade.qty,
                        "SELL" if active_trade.side == "BUY" else "BUY",
                        self.order_type,
                    )
                    active_trade.transaction_cost += close_cost
                    active_trade.exit_time = ts
                    active_trade.exit_price = exit_price
                    active_trade.exit_reason = exit_reason

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
                    active_trade.holding_bars = bars_held

                    # Direction accuracy vs 5-bar forward return
                    if i + 5 < n:
                        future_price = float(ohlcv["close"].iloc[i + 5])
                        actual_ret = (
                            future_price - active_trade.entry_price
                        ) / active_trade.entry_price
                        active_trade.direction_correct = (
                            active_trade.side == "BUY" and actual_ret > 0.005
                        ) or (active_trade.side == "SELL" and actual_ret < -0.005)

                    # MFE/MAE as percentage of entry
                    if active_trade.entry_price > 0:
                        active_trade.mfe_pct = (
                            active_trade.mfe / active_trade.entry_price * 100
                        )
                        active_trade.mae_pct = (
                            active_trade.mae / active_trade.entry_price * 100
                        )

                    cash += (
                        (active_trade.entry_price * active_trade.qty * dir_mult)
                        + pnl_raw
                        - active_trade.transaction_cost
                    )
                    all_trades.append(active_trade)
                    active_trade = None
                    bars_held = 0

            # ── Entry Logic ────────────────────────────────────────
            if active_trade is None:
                pred = self._get_prediction_at(preds, ts)
                if pred is not None:
                    sig = pred.get("signal", "NEUTRAL")
                    kelly_f = float(pred.get("kelly_fraction", 0.0) or 0.0)

                    if sig in SIGNAL_ALL and kelly_f > 0.001:
                        alloc_frac = min(max(0.0, kelly_f), self.kelly_cap)
                        if alloc_frac > 0.001:
                            trade_alloc = cash * alloc_frac
                            qty = int(trade_alloc / price) if price > 0 else 0
                            if qty > 0:
                                side = "BUY" if sig in SIGNAL_BUY else "SELL"
                                target_dist = atr * self.target_atr_mult
                                stop_dist = atr * self.stop_atr_mult
                                target_price = (
                                    (price + target_dist)
                                    if side == "BUY"
                                    else (price - target_dist)
                                )
                                stop_price = (
                                    (price - stop_dist)
                                    if side == "BUY"
                                    else (price + stop_dist)
                                )

                                entry_cost = calculate_indian_transaction_cost(
                                    price, qty, side, self.order_type
                                )
                                opts = self._get_options_at(options, ts)
                                fii = self._get_fii_at(fii_df, ts)

                                active_trade = EnrichedTrade(
                                    symbol=symbol,
                                    side=side,
                                    entry_time=ts,
                                    entry_price=price,
                                    target_price=target_price,
                                    stop_price=stop_price,
                                    qty=qty,
                                    kelly_fraction=alloc_frac,
                                    transaction_cost=entry_cost,
                                    signal=sig,
                                    signal_confidence=float(
                                        pred.get("signal_confidence", 0.0) or 0.0
                                    ),
                                    regime_at_entry=str(regime_labels.iloc[i]),
                                    expected_return=float(
                                        pred.get("expected_return", 0.0) or 0.0
                                    ),
                                    p_up=float(pred.get("p_up", 0.0) or 0.0),
                                    p_down=float(pred.get("p_down", 0.0) or 0.0),
                                    pcr_at_entry=float(opts.get("pcr", 0.0)),
                                    call_wall_at_entry=float(
                                        opts.get("call_wall", 0.0)
                                    ),
                                    put_wall_at_entry=float(opts.get("put_wall", 0.0)),
                                    atm_iv_at_entry=float(opts.get("atm_iv", 0.0)),
                                    gamma_pressure_at_entry=float(
                                        opts.get("gamma_pressure", 0.0)
                                    ),
                                    fii_net_at_entry=fii["fii_net"],
                                    dii_net_at_entry=fii["dii_net"],
                                )
                                bars_held = 0
                                dir_mult = 1.0 if side == "BUY" else -1.0
                                cash -= (price * qty * dir_mult) + entry_cost

            # ── Equity curve ───────────────────────────────────────
            portfolio_val = cash
            if active_trade is not None:
                dir_mult = 1.0 if active_trade.side == "BUY" else -1.0
                portfolio_val += (
                    active_trade.entry_price * active_trade.qty * dir_mult
                ) + ((price - active_trade.entry_price) * active_trade.qty * dir_mult)
            equity_curve.append(portfolio_val)
            per_bar_equity.append(
                {"timestamp": ts.isoformat(), "equity": portfolio_val, "price": price}
            )

        logger.info(f"[Runner] Backtest complete: {len(all_trades)} trades executed")

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "initial_capital": self.initial_capital,
            "final_equity": equity_curve[-1] if equity_curve else self.initial_capital,
            "trades": all_trades,
            "equity_curve": equity_curve,
            "equity_curve_detailed": per_bar_equity,
            "ohlcv": ohlcv,
            "warmup_bars": warmup,
        }
