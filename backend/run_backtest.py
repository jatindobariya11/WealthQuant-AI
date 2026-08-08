"""
WealthQuant Backtesting Engine — CLI Runner
===========================================
Usage:
    python run_backtest.py --symbol NIFTY
    python run_backtest.py --symbol BANKNIFTY --timeframe 15m
    python run_backtest.py --symbol ALL

Options:
    --symbol       NIFTY, BANKNIFTY, or ALL  (default: NIFTY)
    --timeframe    15m, 1h, 1d               (default: 15m)
    --capital      Initial capital in INR    (default: 10000000)
    --kelly-cap    Kelly cap fraction        (default: 0.10)
    --target-atr   Target ATR multiplier     (default: 2.0)
    --stop-atr     Stop ATR multiplier       (default: 1.0)
    --time-exit    Time exit in bars         (default: 5)
    --output       Report output filename    (default: BACKTEST_REPORT.md)
    --no-report    Skip report generation
"""

import argparse
import asyncio
import io
import logging
import os
import sys
import time

# Fix Windows console encoding for rupee/unicode symbols
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest_analyzer import run_full_analysis
from backtest_data_loader import BacktestDataLoader
from backtest_report_generator import generate_report
from backtest_runner import BacktestRunner
from pipeline.db import pipeline_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backtest.cli")

SEPARATOR = "=" * 70


def print_banner(symbol: str, timeframe: str, capital: float):
    print(f"\n{SEPARATOR}")
    print("  WealthQuant Production Backtesting Engine")
    print(f"  Symbol: {symbol}  |  Timeframe: {timeframe}  |  Capital: ₹{capital:,.0f}")
    print("  Data Source: PostgreSQL (wealthquant) — ZERO external API calls")
    print(f"{SEPARATOR}\n")


async def run_single(
    symbol: str,
    timeframe: str,
    capital: float,
    kelly_cap: float,
    target_atr: float,
    stop_atr: float,
    time_exit: int,
    output: str,
    no_report: bool,
) -> dict:

    print(f"\n{'─' * 50}")
    print(f"  Running backtest for: {symbol}/{timeframe}")
    print(f"{'─' * 50}")

    t0 = time.time()

    # Step 1: Connect DB
    print("[1/6] Connecting to PostgreSQL...")
    await pipeline_db.init_pool()
    if not pipeline_db.is_connected:
        print("ERROR: Cannot connect to PostgreSQL. Is it running?")
        sys.exit(1)
    print("  ✓ PostgreSQL connected")

    # Step 2: Load data bundle
    print("[2/6] Loading data from PostgreSQL...")
    loader = BacktestDataLoader(pipeline_db)
    try:
        bundle = await loader.load_backtest_bundle(symbol, timeframe)
    except ValueError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    ohlcv = bundle["ohlcv"]
    preds = bundle["predictions"]
    print(
        f"  ✓ {len(ohlcv)} OHLCV bars ({ohlcv.index[0].date()} to {ohlcv.index[-1].date()})"
    )
    print(f"  ✓ {len(preds)} stored predictions")
    print(f"  ✓ {len(bundle['options_raw'])} options records")
    print(f"  ✓ {len(bundle['fii_dii_raw'])} FII/DII records")

    # Step 3: Data quality audit
    print("[3/6] Running data quality audit...")
    quality = loader.audit_data_quality(bundle)
    grade_icon = {"PASS": "✅", "WARN": "⚠️ ", "FAIL": "❌"}.get(
        quality["quality_grade"], "❓"
    )
    print(
        f"  {grade_icon} Quality Grade: {quality['quality_grade']} ({quality['issue_count']} issues)"
    )
    for issue in quality["issues"]:
        print(f"     → {issue}")

    # Step 4: Run backtest simulation
    print("[4/6] Running bar-by-bar simulation (stored predictions mode)...")
    runner = BacktestRunner(
        initial_capital=capital,
        order_type="INTRADAY",
        kelly_cap=kelly_cap,
        target_atr_mult=target_atr,
        stop_atr_mult=stop_atr,
        time_exit_bars=time_exit,
    )
    run_result = await runner.run_stored_backtest(bundle)
    trades = run_result["trades"]
    print(f"  ✓ Simulation complete: {len(trades)} trades in {time.time() - t0:.1f}s")

    # Step 5: Analysis
    print("[5/6] Computing performance analytics...")
    analysis = run_full_analysis(run_result)
    core = analysis["core_metrics"]
    pnl_icon = "🟢" if core["net_profit"] >= 0 else "🔴"
    print("  ✓ Analysis complete")
    print("\n  ┌─ RESULTS ────────────────────────────────┐")
    print(f"  │  Trades:      {core['total_trades']:<30}│")
    print(f"  │  Win Rate:    {str(core['win_rate']) + '%':<30}│")
    print(
        f"  │  Net Profit:  {pnl_icon} ₹{core['net_profit']:>+,.0f}{' ' * max(0, 20 - len(str(int(abs(core['net_profit'])))))}│"
    )
    print(f"  │  Sharpe:      {core['sharpe_ratio']:<30.4f}│")
    print(f"  │  Max DD:      {str(core['max_drawdown']) + '%':<30}│")
    print("  └───────────────────────────────────────────┘")

    # Step 6: Persist to DB & generate report
    print("[6/6] Generating report...")
    table_counts = await loader.load_all_table_counts()

    if not no_report:
        out = (
            output.replace(".md", f"_{symbol}.md")
            if output == "BACKTEST_REPORT.md"
            else output
        )
        generate_report(
            run_result=run_result,
            analysis=analysis,
            quality_audit=quality,
            table_counts=table_counts,
            wfr_df=bundle.get("walk_forward_results"),
            stage_df=bundle.get("stage_contributions"),
            output_path=out,
        )
        print(f"  ✓ Report written: {out}")

    # Persist result to backtests table
    try:
        import json as _json
        from datetime import date as _date

        async with pipeline_db.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO backtests
                    (name, description, strategy_config, symbols, start_date, end_date,
                     total_return, annualized_return, sharpe_ratio, sortino_ratio,
                     max_drawdown, win_rate, profit_factor, total_trades, results, equity_curve)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)
            """,
                f"WQ_Backtest_{symbol}_{timeframe}",
                f"Production backtest for {symbol} ({timeframe}) using stored predictions",
                _json.dumps(
                    {"kelly_cap": kelly_cap, "timeframe": timeframe, "mode": "stored"}
                ),
                _json.dumps([symbol]),
                ohlcv.index[0].date() if len(ohlcv) > 0 else _date.today(),
                ohlcv.index[-1].date() if len(ohlcv) > 0 else _date.today(),
                float(core.get("total_return_pct", 0)) / 100.0,
                float(core.get("annualized_return_pct", 0)) / 100.0,
                float(core.get("sharpe_ratio", 0)),
                float(core.get("sortino_ratio", 0)),
                float(core.get("max_drawdown", 0)) / 100.0,
                float(core.get("win_rate", 0)) / 100.0,
                float(core.get("profit_factor", 0)),
                int(core.get("total_trades", 0)),
                _json.dumps({"trade_count": len(trades)}),
                _json.dumps({"values": run_result["equity_curve"][:100]}),
            )
        print("  ✓ Result persisted to backtests table")
    except Exception as e:
        print(f"  ⚠️  Could not persist to backtests table: {e}")

    elapsed = time.time() - t0
    print(f"\n  ✅ Backtest for {symbol} completed in {elapsed:.1f}s\n")

    return {"symbol": symbol, "core_metrics": core, "trades": len(trades)}


async def main():
    parser = argparse.ArgumentParser(
        description="WealthQuant Production Backtesting Engine"
    )
    parser.add_argument("--symbol", default="NIFTY", help="NIFTY, BANKNIFTY, or ALL")
    parser.add_argument("--timeframe", default="15m", help="15m, 1h, 1d")
    parser.add_argument("--capital", type=float, default=10_000_000.0)
    parser.add_argument("--kelly-cap", type=float, default=0.10)
    parser.add_argument("--target-atr", type=float, default=2.0)
    parser.add_argument("--stop-atr", type=float, default=1.0)
    parser.add_argument("--time-exit", type=int, default=5)
    parser.add_argument("--output", default="BACKTEST_REPORT.md")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()

    symbols = (
        ["NIFTY", "BANKNIFTY"]
        if args.symbol.upper() == "ALL"
        else [args.symbol.upper()]
    )

    print_banner(args.symbol.upper(), args.timeframe, args.capital)

    all_results = []
    for sym in symbols:
        result = await run_single(
            symbol=sym,
            timeframe=args.timeframe,
            capital=args.capital,
            kelly_cap=args.kelly_cap,
            target_atr=args.target_atr,
            stop_atr=args.stop_atr,
            time_exit=args.time_exit,
            output=args.output,
            no_report=args.no_report,
        )
        all_results.append(result)

    await pipeline_db.close()

    print(f"\n{SEPARATOR}")
    print("  BACKTEST COMPLETE")
    print(f"{SEPARATOR}")
    for r in all_results:
        c = r["core_metrics"]
        icon = "🟢" if c.get("net_profit", 0) >= 0 else "🔴"
        print(
            f"  {r['symbol']:12s} | Trades: {r['trades']:4d} | "
            f"Win: {c.get('win_rate', 0):.1f}% | "
            f"P&L: {icon} ₹{c.get('net_profit', 0):+,.0f} | "
            f"Sharpe: {c.get('sharpe_ratio', 0):.3f}"
        )
    print(f"{SEPARATOR}\n")


if __name__ == "__main__":
    asyncio.run(main())
