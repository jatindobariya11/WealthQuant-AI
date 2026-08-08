"""
WealthQuant Backtesting Engine — Report Generator
==================================================
Generates BACKTEST_REPORT.md with 14 comprehensive sections.
"""

import logging
from datetime import datetime

logger = logging.getLogger("backtest.report")


def _fmt_inr(v):
    if abs(v) >= 1e7:
        return f"INR {v / 1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"INR {v / 1e5:.2f} L"
    return f"INR {v:,.0f}"


def _pct(v):
    return f"{v:.2f}%"


def _sign(v):
    return f"+{v:.2f}" if v >= 0 else f"{v:.2f}"


def generate_report(
    run_result: dict,
    analysis: dict,
    quality_audit: dict,
    table_counts: dict,
    wfr_df=None,
    stage_df=None,
    output_path: str = "BACKTEST_REPORT.md",
) -> str:
    """Generate the full BACKTEST_REPORT.md and return the path."""
    trades = run_result["trades"]
    symbol = run_result["symbol"]
    timeframe = run_result["timeframe"]
    initial = run_result["initial_capital"]
    final = run_result["final_equity"]
    core = analysis["core_metrics"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S IST")

    lines = []
    A = lines.append

    # ── HEADER ─────────────────────────────────────────────────────
    A("# WealthQuant Backtest Report")
    A("")
    A(f"**Symbol:** {symbol} | **Timeframe:** {timeframe} | **Generated:** {now}")
    A("")
    A("**Data Source:** PostgreSQL (wealthquant) | **Mode:** Stored Predictions")
    A("")
    A("---")
    A("")

    # ── SECTION 1: EXECUTIVE SUMMARY ───────────────────────────────
    A("## 1. Executive Summary")
    A("")
    pnl_color = "🟢" if core["net_profit"] >= 0 else "🔴"
    A("| Metric | Value |")
    A("|--------|-------|")
    A(f"| Initial Capital | {_fmt_inr(initial)} |")
    A(f"| Final Equity | {_fmt_inr(final)} |")
    A(
        f"| Net Profit/Loss | {pnl_color} {_fmt_inr(core['net_profit'])} ({_sign(core['total_return_pct'])}%) |"
    )
    A(f"| Total Trades | {core['total_trades']} |")
    A(f"| Win Rate | {_pct(core['win_rate'])} |")
    A(f"| Sharpe Ratio | {core['sharpe_ratio']:.4f} |")
    A(f"| Max Drawdown | {_pct(core['max_drawdown'])} |")
    A(f"| Data Quality | {quality_audit['quality_grade']} |")
    A("")
    A("---")
    A("")

    # ── SECTION 2: PERFORMANCE METRICS ─────────────────────────────
    A("## 2. Performance Metrics")
    A("")
    A("| Metric | Value |")
    A("|--------|-------|")
    metrics_display = [
        ("Total Trades", str(core["total_trades"])),
        ("Win Rate", _pct(core["win_rate"])),
        ("Loss Rate", _pct(core["loss_rate"])),
        ("Net Profit", _fmt_inr(core["net_profit"])),
        ("Gross Profit", _fmt_inr(core["gross_profit"])),
        ("Gross Loss", _fmt_inr(core["gross_loss"])),
        ("Average Winner", _fmt_inr(core["average_winner"])),
        ("Average Loser", _fmt_inr(core["average_loser"])),
        ("Largest Winner", _fmt_inr(core["largest_winner"])),
        ("Largest Loser", _fmt_inr(core["largest_loser"])),
        ("Sharpe Ratio", f"{core['sharpe_ratio']:.4f}"),
        ("Sortino Ratio", f"{core['sortino_ratio']:.4f}"),
        ("Profit Factor", f"{core['profit_factor']:.3f}"),
        ("Max Drawdown", _pct(core["max_drawdown"])),
        ("Expectancy per Trade", _fmt_inr(core["expectancy"])),
        ("Avg Holding (bars)", str(core["avg_holding_bars"])),
        ("Risk/Reward Ratio", f"{core['risk_reward']:.3f}"),
        ("Consecutive Wins", str(core["consecutive_wins"])),
        ("Consecutive Losses", str(core["consecutive_losses"])),
        ("Total Return", _pct(core["total_return_pct"])),
        ("Annualized Return", _pct(core["annualized_return_pct"])),
        ("Transaction Costs", _fmt_inr(core["total_transaction_costs"])),
    ]
    for name, val in metrics_display:
        A(f"| {name} | {val} |")
    A("")
    A("---")
    A("")

    # ── SECTION 3: MONTHLY RETURNS ──────────────────────────────────
    A("## 3. Monthly Returns")
    A("")
    monthly = analysis.get("monthly_returns", [])
    if monthly:
        A("| Month | Net P&L | Trades | Win Rate |")
        A("|-------|---------|--------|----------|")
        for row in monthly:
            pnl_icon = "🟢" if row["net_pnl"] >= 0 else "🔴"
            A(
                f"| {row['month']} | {pnl_icon} {_fmt_inr(row['net_pnl'])} | {row['trades']} | {_pct(row.get('win_rate', 0))} |"
            )
    else:
        A("*No completed trades to compute monthly returns.*")
    A("")
    A("---")
    A("")

    # ── SECTION 4: EQUITY CURVE SUMMARY ────────────────────────────
    A("## 4. Equity Curve Summary")
    A("")
    eq = run_result.get("equity_curve", [])
    if eq:
        eq_peak = max(eq)
        eq_trough = min(eq)
        A("| | Value |")
        A("|---|---|")
        A(f"| Starting NAV | {_fmt_inr(initial)} |")
        A(f"| Peak NAV | {_fmt_inr(eq_peak)} |")
        A(f"| Trough NAV | {_fmt_inr(eq_trough)} |")
        A(f"| Final NAV | {_fmt_inr(eq[-1])} |")
        A(f"| Total Bars | {len(eq)} |")
        A(f"| Max Drawdown | {_pct(core['max_drawdown'])} |")
    A("")
    A("---")
    A("")

    # ── SECTION 5: REGIME PERFORMANCE ──────────────────────────────
    A("## 5. Regime Performance")
    A("")
    regime = analysis.get("regime_breakdown", {})
    if regime:
        A("| Regime | Trades | Win Rate | Net P&L | Profit Factor | Avg Hold |")
        A("|--------|--------|----------|---------|---------------|----------|")
        for r_name, r_stats in regime.items():
            A(
                f"| {r_name} | {r_stats['total_trades']} | "
                f"{_pct(r_stats['win_rate'])} | {_fmt_inr(r_stats['net_profit'])} | "
                f"{r_stats['profit_factor']:.3f} | {r_stats['avg_holding_bars']} bars |"
            )
    else:
        A("*No regime data available.*")
    A("")
    A("---")
    A("")

    # ── SECTION 6: PREDICTION ACCURACY ─────────────────────────────
    A("## 6. Prediction Accuracy")
    A("")
    mfe_mae = analysis.get("mfe_mae_stats", {})
    qs = quality_audit.get("stats", {})
    A("| Metric | Value |")
    A("|--------|-------|")
    A(f"| Total Predictions Stored | {qs.get('total_predictions', 'N/A')} |")
    A(f"| Predictions Evaluated | {qs.get('predictions_evaluated', 'N/A')} |")
    A(f"| Raw DB Accuracy | {qs.get('raw_accuracy', 'N/A')}% |")
    A(
        f"| Direction Correct (backtest) | {sum(1 for t in trades if t.direction_correct)} / {len(trades)} trades |"
    )
    A(f"| Target Hit Rate | {mfe_mae.get('target_hit_rate', 0.0)}% |")
    A(f"| Stop Hit Rate | {mfe_mae.get('stop_hit_rate', 0.0)}% |")
    A(
        f"| Avg MFE | {mfe_mae.get('avg_mfe_pct', 0.0)}% ({mfe_mae.get('avg_mfe_pts', 0.0)} pts) |"
    )
    A(
        f"| Avg MAE | {mfe_mae.get('avg_mae_pct', 0.0)}% ({mfe_mae.get('avg_mae_pts', 0.0)} pts) |"
    )
    A(f"| Max MFE | {mfe_mae.get('max_mfe_pct', 0.0)}% |")
    A(f"| Max MAE | {mfe_mae.get('max_mae_pct', 0.0)}% |")
    A("")
    A("### Exit Reason Breakdown")
    A("")
    exit_br = analysis.get("exit_reason_breakdown", {})
    if exit_br:
        A("| Exit Reason | Count | Win Rate | Net P&L |")
        A("|-------------|-------|----------|---------|")
        for reason, stats in exit_br.items():
            A(
                f"| {reason} | {stats['count']} | {_pct(stats['win_rate'])} | {_fmt_inr(stats['net_pnl'])} |"
            )
    A("")
    A("---")
    A("")

    # ── SECTION 7: OPTIONS CONTRIBUTION ────────────────────────────
    A("## 7. Options Contribution Analysis")
    A("")
    opts = analysis.get("options_contribution", {})
    if opts:
        A("| Condition | Trades | Win Rate | Profit Factor |")
        A("|-----------|--------|----------|---------------|")
        rows_to_show = [
            ("With Options Data", "with_options_data"),
            ("Without Options Data", "without_options_data"),
            ("PCR >= 1.2 (Bullish)", "pcr_high_ge_1_2"),
            ("PCR 0.8-1.2 (Neutral)", "pcr_mid_0_8_to_1_2"),
            ("PCR <= 0.8 (Bearish)", "pcr_low_le_0_8"),
            ("Near Call Wall", "near_call_wall"),
            ("Near Put Wall", "near_put_wall"),
            ("ATM IV > 25%", "high_iv_gt_25pct"),
            ("ATM IV 15-25%", "mid_iv_15_25pct"),
            ("ATM IV < 15%", "low_iv_lt_15pct"),
            ("FII Net Positive", "fii_net_positive"),
            ("FII Net Negative", "fii_net_negative"),
            ("DII Net Positive", "dii_net_positive"),
        ]
        for label, key in rows_to_show:
            d = opts.get(key, {})
            if d.get("count", 0) > 0:
                A(
                    f"| {label} | {d.get('count', 0)} | "
                    f"{_pct(d.get('win_rate', 0))} | "
                    f"{d.get('profit_factor', 'N/A')} |"
                )
    A("")
    A("---")
    A("")

    # ── SECTION 8: BEST 5 TRADES ────────────────────────────────────
    A("## 8. Best 5 Trades")
    A("")
    best = analysis.get("best_trades", [])
    if best:
        A("| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |")
        A("|------------|--------|------|-------|------|-----|-------------|--------|")
        for t in best:
            A(
                f"| {t['entry_time'][:16]} | {t['signal']} | {t['side']} | "
                f"{t['entry_price']:,.1f} | {t['exit_price']:,.1f} | "
                f"🟢 {_fmt_inr(t['realized_pnl'])} | {t['exit_reason']} | {t['regime']} |"
            )
    A("")

    # ── SECTION 9: WORST 5 TRADES ───────────────────────────────────
    A("## 9. Worst 5 Trades")
    A("")
    worst = analysis.get("worst_trades", [])
    if worst:
        A("| Entry Time | Signal | Side | Entry | Exit | P&L | Exit Reason | Regime |")
        A("|------------|--------|------|-------|------|-----|-------------|--------|")
        for t in worst:
            A(
                f"| {t['entry_time'][:16]} | {t['signal']} | {t['side']} | "
                f"{t['entry_price']:,.1f} | {t['exit_price']:,.1f} | "
                f"🔴 {_fmt_inr(t['realized_pnl'])} | {t['exit_reason']} | {t['regime']} |"
            )
    A("")
    A("---")
    A("")

    # ── SECTION 10: TOP FAILURE REASONS ─────────────────────────────
    A("## 10. Top Failure Reasons")
    A("")
    losing_trades = [t for t in trades if t.realized_pnl < 0]
    if losing_trades:
        # Group losses by regime
        loss_by_regime = {}
        for t in losing_trades:
            r = t.regime_at_entry
            loss_by_regime.setdefault(r, 0)
            loss_by_regime[r] += 1
        sorted_failures = sorted(loss_by_regime.items(), key=lambda x: -x[1])
        A("| Regime | Losing Trades | Notes |")
        A("|--------|--------------|-------|")
        for regime, cnt in sorted_failures:
            pct = round(cnt / len(losing_trades) * 100, 1)
            A(f"| {regime} | {cnt} ({pct}%) | Worst performing regime |")

        # Loss by exit reason
        A("")
        A("### Losses by Exit Reason")
        A("")
        loss_by_exit = {}
        for t in losing_trades:
            r = t.exit_reason or "UNKNOWN"
            loss_by_exit.setdefault(r, {"count": 0, "total_loss": 0.0})
            loss_by_exit[r]["count"] += 1
            loss_by_exit[r]["total_loss"] += t.realized_pnl
        A("| Exit Reason | Losing Trades | Total Loss |")
        A("|-------------|--------------|------------|")
        for reason, stats in sorted(
            loss_by_exit.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            A(f"| {reason} | {stats['count']} | {_fmt_inr(stats['total_loss'])} |")
    else:
        A("*No losing trades — all trades were profitable.*")
    A("")
    A("---")
    A("")

    # ── SECTION 11: DATA QUALITY REPORT ─────────────────────────────
    A("## 11. Data Quality Report")
    A("")
    grade = quality_audit["quality_grade"]
    grade_icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(grade, "❓")
    A(f"**Overall Grade:** {grade_icon} {grade}")
    A("")
    qs = quality_audit.get("stats", {})
    A("| Check | Result |")
    A("|-------|--------|")
    A(f"| OHLCV Bars | {qs.get('ohlcv_total_bars', 'N/A')} |")
    A(f"| Date Range | {qs.get('ohlcv_date_range', 'N/A')} |")
    A(f"| Trading Days | {qs.get('ohlcv_trading_days', 'N/A')} |")
    A(f"| Missing Candles | {qs.get('ohlcv_missing_candles', 0)} |")
    A(f"| OHLCV Duplicates | {qs.get('ohlcv_duplicates', 0)} |")
    A(f"| Predictions Stored | {qs.get('total_predictions', 0)} |")
    A(f"| Prediction Gaps | {qs.get('prediction_gaps', 0)} |")
    A(f"| Options Coverage | {qs.get('options_coverage_pct', 0.0)}% |")
    A(
        f"| FII/DII Coverage | {qs.get('fii_dii_coverage_pct', 0.0)}% ({qs.get('fii_dii_available_days', 0)}/{qs.get('fii_dii_trading_days', 0)} days) |"
    )
    A(f"| Raw DB Accuracy | {qs.get('raw_accuracy', 'N/A')}% |")
    if quality_audit.get("issues"):
        A("")
        A("**Issues Detected:**")
        A("")
        for issue in quality_audit["issues"]:
            A(f"- ⚠️ {issue}")
    A("")
    A("---")
    A("")

    # ── SECTION 12: DATABASE STATISTICS ─────────────────────────────
    A("## 12. Database Statistics")
    A("")
    A(
        f"**Database:** PostgreSQL (wealthquant) | **Total Rows:** {sum(v for v in table_counts.values() if v > 0):,}"
    )
    A("")
    A("| Table | Rows |")
    A("|-------|------|")
    for table, count in sorted(table_counts.items(), key=lambda x: -x[1]):
        if count >= 0:
            A(f"| `{table}` | {count:,} |")
    A("")
    A("---")
    A("")

    # ── SECTION 13: WALK-FORWARD VALIDATION SUMMARY ─────────────────
    A("## 13. Walk-Forward Validation Summary")
    A("")
    if wfr_df is not None and not wfr_df.empty:
        A("| Fold | Accuracy | F1 Score | Sharpe | Max Drawdown |")
        A("|------|----------|----------|--------|--------------|")
        for _, row in wfr_df.iterrows():
            A(
                f"| {row.get('fold_index', '?')} | "
                f"{round(float(row.get('accuracy', 0) or 0) * 100, 1)}% | "
                f"{round(float(row.get('f1_score', 0) or 0), 4)} | "
                f"{round(float(row.get('sharpe_ratio', 0) or 0), 4)} | "
                f"{round(float(row.get('max_drawdown', 0) or 0) * 100, 2)}% |"
            )
    else:
        A("*No walk-forward validation results available.*")
    A("")
    A("---")
    A("")

    # ── SECTION 14: STAGE CONTRIBUTIONS ─────────────────────────────
    A("## 14. Stage Contributions")
    A("")
    if stage_df is not None and not stage_df.empty:
        A("| Stage | Accuracy | Correlation | MAE | Sharpe Contribution | Status |")
        A("|-------|----------|-------------|-----|---------------------|--------|")
        for _, row in stage_df.iterrows():
            A(
                f"| {row.get('stage', '?')} | "
                f"{round(float(row.get('accuracy', 0) or 0) * 100, 1)}% | "
                f"{round(float(row.get('correlation', 0) or 0), 4)} | "
                f"{round(float(row.get('mae', 0) or 0), 6)} | "
                f"{round(float(row.get('sharpe_contribution', 0) or 0), 4)} | "
                f"{row.get('status', 'N/A')} |"
            )
    else:
        A("*No stage contribution data available.*")
    A("")
    A("---")
    A("")
    A(f"*Report generated by WealthQuant Backtesting Engine — {now}*")
    A("*All data sourced exclusively from PostgreSQL — zero external API calls.*")

    report_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    logger.info(
        f"[Report] BACKTEST_REPORT.md written to {output_path} ({len(report_text)} chars)"
    )
    return output_path
