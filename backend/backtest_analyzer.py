"""
WealthQuant Backtesting Engine — Performance Analyzer
======================================================
Computes all 20+ performance metrics, regime breakdown, options contribution
analysis, monthly returns, consecutive win/loss streaks, and MFE/MAE stats.
"""

import logging

import numpy as np
import pandas as pd

from backtest_runner import EnrichedTrade

logger = logging.getLogger("backtest.analyzer")

REGIMES = [
    "TRENDING_BULL",
    "TRENDING_BEAR",
    "MEAN_REVERTING",
    "HIGH_VOLATILITY",
    "LOW_VOLATILITY",
    "TRANSITION",
    "UNKNOWN",
]


def _safe_div(a, b, default=0.0):
    return a / b if b and b != 0 else default


def compute_core_metrics(
    trades: list[EnrichedTrade],
    initial_capital: float,
    equity_curve: list[float],
    timeframe: str = "15m",
) -> dict:
    """Compute all 20 core performance metrics from a list of EnrichedTrade objects."""
    if not trades:
        return {
            "total_trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "net_profit": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "average_winner": 0.0,
            "average_loser": 0.0,
            "largest_winner": 0.0,
            "largest_loser": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "expectancy": 0.0,
            "avg_holding_bars": 0.0,
            "risk_reward": 0.0,
            "consecutive_wins": 0,
            "consecutive_losses": 0,
            "total_return_pct": 0.0,
            "annualized_return_pct": 0.0,
            "total_transaction_costs": 0.0,
        }

    pnls = [t.realized_pnl for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    total_trades = len(trades)
    win_rate = _safe_div(len(wins), total_trades)
    loss_rate = 1.0 - win_rate

    net_profit = sum(pnls)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    avg_winner = _safe_div(gross_profit, len(wins))
    avg_loser = _safe_div(gross_loss, len(losses))

    profit_factor = _safe_div(
        gross_profit, gross_loss, default=float("inf") if gross_profit > 0 else 1.0
    )
    expectancy = (win_rate * avg_winner) - (loss_rate * avg_loser)
    risk_reward = _safe_div(avg_winner, avg_loser)

    largest_winner = max(pnls) if pnls else 0.0
    largest_loser = min(pnls) if pnls else 0.0

    avg_holding_bars = _safe_div(sum(t.holding_bars for t in trades), total_trades)

    # Consecutive wins/losses
    max_consec_wins = max_consec_losses = cur_w = cur_l = 0
    for p in pnls:
        if p > 0:
            cur_w += 1
            cur_l = 0
        else:
            cur_l += 1
            cur_w = 0
        max_consec_wins = max(max_consec_wins, cur_w)
        max_consec_losses = max(max_consec_losses, cur_l)

    # Equity curve metrics
    if equity_curve and len(equity_curve) > 1:
        eq_series = pd.Series(equity_curve)
        eq_returns = eq_series.pct_change().fillna(0.0)
        total_return = _safe_div(equity_curve[-1] - initial_capital, initial_capital)

        # Annualization factor
        bars_per_year = {"15m": 252 * 25, "1h": 252 * 6.25, "1d": 252}.get(
            timeframe, 252 * 25
        )
        ann_return = float(
            (1.0 + total_return) ** (bars_per_year / len(equity_curve)) - 1.0
        )
        ann_vol = float(eq_returns.std() * np.sqrt(bars_per_year))
        sharpe = _safe_div(ann_return, ann_vol)

        downside = eq_returns[eq_returns < 0]
        down_std = (
            float(downside.std() * np.sqrt(bars_per_year)) if len(downside) > 1 else 0.0
        )
        sortino = _safe_div(ann_return, down_std)

        peaks = eq_series.cummax()
        drawdowns = (peaks - eq_series) / peaks.replace(0, np.nan)
        max_dd = float(drawdowns.max())
    else:
        total_return = ann_return = ann_vol = sharpe = sortino = max_dd = 0.0

    total_costs = sum(t.transaction_cost for t in trades)

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate * 100, 2),
        "loss_rate": round(loss_rate * 100, 2),
        "net_profit": round(net_profit, 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "average_winner": round(avg_winner, 2),
        "average_loser": round(avg_loser, 2),
        "largest_winner": round(largest_winner, 2),
        "largest_loser": round(largest_loser, 2),
        "sharpe_ratio": round(sharpe, 4),
        "sortino_ratio": round(sortino, 4),
        "profit_factor": round(profit_factor, 4),
        "max_drawdown": round(max_dd * 100, 2),
        "expectancy": round(expectancy, 2),
        "avg_holding_bars": round(avg_holding_bars, 1),
        "risk_reward": round(risk_reward, 3),
        "consecutive_wins": max_consec_wins,
        "consecutive_losses": max_consec_losses,
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(ann_return * 100, 2),
        "total_transaction_costs": round(total_costs, 2),
    }


def compute_regime_breakdown(
    trades: list[EnrichedTrade], initial_capital: float
) -> dict:
    """Compute per-regime performance statistics."""
    result = {}
    for regime in REGIMES:
        regime_trades = [t for t in trades if t.regime_at_entry == regime]
        if not regime_trades:
            continue
        pnls = [t.realized_pnl for t in regime_trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        result[regime] = {
            "total_trades": len(regime_trades),
            "win_rate": round(_safe_div(len(wins), len(regime_trades)) * 100, 1),
            "net_profit": round(sum(pnls), 2),
            "profit_factor": round(_safe_div(sum(wins), abs(sum(losses))), 3),
            "avg_winner": round(_safe_div(sum(wins), max(len(wins), 1)), 2),
            "avg_loser": round(_safe_div(abs(sum(losses)), max(len(losses), 1)), 2),
            "avg_holding_bars": round(
                _safe_div(
                    sum(t.holding_bars for t in regime_trades), len(regime_trades)
                ),
                1,
            ),
        }
    return result


def compute_options_contribution(trades: list[EnrichedTrade]) -> dict:
    """Analyze how options data availability and conditions affect prediction quality."""
    with_opts = [t for t in trades if t.pcr_at_entry > 0.0]
    without_opts = [t for t in trades if t.pcr_at_entry == 0.0]

    def win_rate_of(trade_list):
        if not trade_list:
            return 0.0
        wins = sum(1 for t in trade_list if t.realized_pnl > 0)
        return round(wins / len(trade_list) * 100, 1)

    def profit_factor_of(trade_list):
        if not trade_list:
            return 0.0
        gp = sum(t.realized_pnl for t in trade_list if t.realized_pnl > 0)
        gl = abs(sum(t.realized_pnl for t in trade_list if t.realized_pnl < 0))
        return round(_safe_div(gp, gl), 3)

    # PCR segmentation
    high_pcr = [t for t in with_opts if t.pcr_at_entry >= 1.2]
    low_pcr = [t for t in with_opts if t.pcr_at_entry <= 0.8]
    mid_pcr = [t for t in with_opts if 0.8 < t.pcr_at_entry < 1.2]

    # Near-wall analysis
    def near_wall(t: EnrichedTrade, pct: float = 0.01) -> str:
        if (
            t.call_wall_at_entry > 0
            and abs(t.entry_price - t.call_wall_at_entry) / t.entry_price <= pct
        ):
            return "CALL_WALL"
        if (
            t.put_wall_at_entry > 0
            and abs(t.entry_price - t.put_wall_at_entry) / t.entry_price <= pct
        ):
            return "PUT_WALL"
        return "NONE"

    near_call_wall = [t for t in with_opts if near_wall(t) == "CALL_WALL"]
    near_put_wall = [t for t in with_opts if near_wall(t) == "PUT_WALL"]

    # ATM IV segmentation (low <15%, mid 15-25%, high >25%)
    high_iv = [t for t in with_opts if t.atm_iv_at_entry > 0.25]
    mid_iv = [t for t in with_opts if 0.15 <= t.atm_iv_at_entry <= 0.25]
    low_iv = [t for t in with_opts if 0 < t.atm_iv_at_entry < 0.15]

    # FII/DII contribution
    fii_bullish = [t for t in trades if t.fii_net_at_entry > 0]
    fii_bearish = [t for t in trades if t.fii_net_at_entry < 0]
    dii_bullish = [t for t in trades if t.dii_net_at_entry > 0]

    return {
        "with_options_data": {
            "count": len(with_opts),
            "win_rate": win_rate_of(with_opts),
            "profit_factor": profit_factor_of(with_opts),
        },
        "without_options_data": {
            "count": len(without_opts),
            "win_rate": win_rate_of(without_opts),
            "profit_factor": profit_factor_of(without_opts),
        },
        "pcr_high_ge_1_2": {
            "count": len(high_pcr),
            "win_rate": win_rate_of(high_pcr),
            "profit_factor": profit_factor_of(high_pcr),
        },
        "pcr_mid_0_8_to_1_2": {
            "count": len(mid_pcr),
            "win_rate": win_rate_of(mid_pcr),
            "profit_factor": profit_factor_of(mid_pcr),
        },
        "pcr_low_le_0_8": {
            "count": len(low_pcr),
            "win_rate": win_rate_of(low_pcr),
            "profit_factor": profit_factor_of(low_pcr),
        },
        "near_call_wall": {
            "count": len(near_call_wall),
            "win_rate": win_rate_of(near_call_wall),
            "profit_factor": profit_factor_of(near_call_wall),
        },
        "near_put_wall": {
            "count": len(near_put_wall),
            "win_rate": win_rate_of(near_put_wall),
            "profit_factor": profit_factor_of(near_put_wall),
        },
        "high_iv_gt_25pct": {
            "count": len(high_iv),
            "win_rate": win_rate_of(high_iv),
            "profit_factor": profit_factor_of(high_iv),
        },
        "mid_iv_15_25pct": {
            "count": len(mid_iv),
            "win_rate": win_rate_of(mid_iv),
            "profit_factor": profit_factor_of(mid_iv),
        },
        "low_iv_lt_15pct": {
            "count": len(low_iv),
            "win_rate": win_rate_of(low_iv),
            "profit_factor": profit_factor_of(low_iv),
        },
        "fii_net_positive": {
            "count": len(fii_bullish),
            "win_rate": win_rate_of(fii_bullish),
        },
        "fii_net_negative": {
            "count": len(fii_bearish),
            "win_rate": win_rate_of(fii_bearish),
        },
        "dii_net_positive": {
            "count": len(dii_bullish),
            "win_rate": win_rate_of(dii_bullish),
        },
    }


def compute_monthly_returns(trades: list[EnrichedTrade]) -> list:
    """Compute month-by-month P&L breakdown."""
    if not trades:
        return []
    records = []
    for t in trades:
        if t.exit_time is None:
            continue
        month_key = (
            t.exit_time.strftime("%Y-%m")
            if hasattr(t.exit_time, "strftime")
            else str(t.exit_time)[:7]
        )
        records.append({"month": month_key, "pnl": t.realized_pnl})

    df = pd.DataFrame(records)
    if df.empty:
        return []
    monthly = (
        df.groupby("month")["pnl"]
        .agg(
            net_pnl="sum",
            trades="count",
            wins=lambda x: (x > 0).sum(),
            losses=lambda x: (x <= 0).sum(),
        )
        .reset_index()
    )
    monthly["win_rate"] = (monthly["wins"] / monthly["trades"] * 100).round(1)
    return monthly.to_dict(orient="records")


def compute_prediction_analysis(trades: list[EnrichedTrade]) -> list:
    """Per-prediction detailed analysis record."""
    results = []
    for t in trades:
        results.append(
            {
                "entry_time": str(t.entry_time),
                "exit_time": str(t.exit_time),
                "signal": t.signal,
                "confidence": round(t.signal_confidence, 4),
                "side": t.side,
                "entry_price": round(t.entry_price, 2),
                "exit_price": round(t.exit_price, 2),
                "target_price": round(t.target_price, 2),
                "stop_price": round(t.stop_price, 2),
                "qty": t.qty,
                "realized_pnl": round(t.realized_pnl, 2),
                "returns_pct": round(t.returns * 100, 3),
                "target_hit": t.target_hit,
                "stop_hit": t.stop_hit,
                "exit_reason": t.exit_reason,
                "holding_bars": t.holding_bars,
                "mfe_pts": round(t.mfe, 2),
                "mae_pts": round(t.mae, 2),
                "mfe_pct": round(t.mfe_pct, 3),
                "mae_pct": round(t.mae_pct, 3),
                "direction_correct": t.direction_correct,
                "regime": t.regime_at_entry,
                "pcr": round(t.pcr_at_entry, 3),
                "atm_iv": round(t.atm_iv_at_entry, 3),
                "fii_net": round(t.fii_net_at_entry, 2),
                "dii_net": round(t.dii_net_at_entry, 2),
            }
        )
    return results


def compute_exit_reason_breakdown(trades: list[EnrichedTrade]) -> dict:
    """Break down trades by exit reason."""
    reasons = {}
    for t in trades:
        r = t.exit_reason or "UNKNOWN"
        if r not in reasons:
            reasons[r] = {"count": 0, "wins": 0, "net_pnl": 0.0}
        reasons[r]["count"] += 1
        if t.realized_pnl > 0:
            reasons[r]["wins"] += 1
        reasons[r]["net_pnl"] += t.realized_pnl

    for r in reasons:
        cnt = reasons[r]["count"]
        reasons[r]["win_rate"] = round(_safe_div(reasons[r]["wins"], cnt) * 100, 1)
        reasons[r]["net_pnl"] = round(reasons[r]["net_pnl"], 2)
    return reasons


def compute_mfe_mae_stats(trades: list[EnrichedTrade]) -> dict:
    """Aggregate MFE/MAE statistics."""
    if not trades:
        return {}
    mfe_pcts = [t.mfe_pct for t in trades]
    mae_pcts = [t.mae_pct for t in trades]
    return {
        "avg_mfe_pct": round(float(np.mean(mfe_pcts)), 3),
        "avg_mae_pct": round(float(np.mean(mae_pcts)), 3),
        "max_mfe_pct": round(float(np.max(mfe_pcts)), 3),
        "max_mae_pct": round(float(np.max(mae_pcts)), 3),
        "avg_mfe_pts": round(float(np.mean([t.mfe for t in trades])), 2),
        "avg_mae_pts": round(float(np.mean([t.mae for t in trades])), 2),
        "target_hit_rate": round(
            sum(1 for t in trades if t.target_hit) / len(trades) * 100, 1
        ),
        "stop_hit_rate": round(
            sum(1 for t in trades if t.stop_hit) / len(trades) * 100, 1
        ),
    }


def run_full_analysis(run_result: dict) -> dict:
    """Run all analysis functions on a backtest run result and return combined report."""
    trades = run_result["trades"]
    equity_curve = run_result["equity_curve"]
    initial_cap = run_result["initial_capital"]
    timeframe = run_result["timeframe"]

    core = compute_core_metrics(trades, initial_cap, equity_curve, timeframe)
    regime = compute_regime_breakdown(trades, initial_cap)
    options = compute_options_contribution(trades)
    monthly = compute_monthly_returns(trades)
    per_pred = compute_prediction_analysis(trades)
    exit_br = compute_exit_reason_breakdown(trades)
    mfe_mae = compute_mfe_mae_stats(trades)

    # Best / worst trades
    sorted_trades = sorted(trades, key=lambda t: t.realized_pnl, reverse=True)
    best_trades = compute_prediction_analysis(sorted_trades[:5])
    worst_trades = compute_prediction_analysis(
        sorted_trades[-5:] if len(sorted_trades) >= 5 else sorted_trades
    )

    return {
        "core_metrics": core,
        "regime_breakdown": regime,
        "options_contribution": options,
        "monthly_returns": monthly,
        "prediction_analysis": per_pred,
        "exit_reason_breakdown": exit_br,
        "mfe_mae_stats": mfe_mae,
        "best_trades": best_trades,
        "worst_trades": worst_trades,
    }
