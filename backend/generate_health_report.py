#!/usr/bin/env python3
"""
WealthQuant V7.1 — Options Data Warehouse Health Report Generator
=================================================================

Connects to PostgreSQL, queries all options data tables, computes health
metrics, and generates a beautifully formatted Markdown report.

Usage:
    python generate_health_report.py
    python generate_health_report.py --output /path/to/report.md
"""

import argparse
import asyncio
import os
import sys
from datetime import date, datetime, timedelta

import asyncpg
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Windows terminal encoding (cp1252 cannot encode emojis)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

DEFAULT_OUTPUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "OPTIONS_DATA_HEALTH_REPORT.md",
)

TABLES = ["options_history", "strike_history", "wall_history", "pcr_history"]

ACCUMULATION_TARGET_MIN = 90
ACCUMULATION_TARGET_MAX = 180


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weekdays_between(start: date, end: date) -> list[date]:
    """Return all weekdays (Mon-Fri) between *start* and *end* inclusive."""
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon=0 … Fri=4
            days.append(current)
        current += timedelta(days=1)
    return days


def _progress_bar(current: int, target: int, width: int = 30) -> str:
    """Render a text-based progress bar."""
    if target <= 0:
        pct = 0.0
    else:
        pct = min(current / target, 1.0)
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"`[{bar}]` **{pct:.0%}**"


def _fmt(n) -> str:
    """Format a number with comma separators, or '—' if None."""
    if n is None:
        return "—"
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


# ---------------------------------------------------------------------------
# Data-fetching coroutines
# ---------------------------------------------------------------------------


async def _fetch_table_row_counts(conn: asyncpg.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in TABLES:
        row = await conn.fetchrow(f"SELECT COUNT(*) AS cnt FROM {table}")
        counts[table] = row["cnt"]
    return counts


async def _fetch_symbols(conn: asyncpg.Connection) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT symbol FROM options_history ORDER BY symbol"
    )
    return [r["symbol"] for r in rows]


async def _fetch_date_range(
    conn: asyncpg.Connection, symbol: str
) -> tuple[date | None, date | None]:
    row = await conn.fetchrow(
        "SELECT MIN(date) AS first_date, MAX(date) AS last_date "
        "FROM options_history WHERE symbol = $1",
        symbol,
    )
    return row["first_date"], row["last_date"]


async def _fetch_actual_dates(conn: asyncpg.Connection, symbol: str) -> list[date]:
    rows = await conn.fetch(
        "SELECT DISTINCT date FROM options_history WHERE symbol = $1 ORDER BY date",
        symbol,
    )
    return [r["date"] for r in rows]


async def _fetch_strike_stats(conn: asyncpg.Connection, symbol: str) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            AVG(cnt)             AS avg_strikes,
            MIN(cnt)             AS min_strikes,
            MAX(cnt)             AS max_strikes,
            SUM(cnt)             AS total_rows,
            COUNT(DISTINCT strike_val) AS unique_strikes
        FROM (
            SELECT date, COUNT(*) AS cnt, strike AS strike_val
            FROM strike_history
            WHERE symbol = $1
            GROUP BY date, strike
        ) sub
        """,
        symbol,
    )
    # The subquery above groups by (date, strike), so we need a slightly
    # different approach: strikes-per-day vs unique strikes overall.
    per_day = await conn.fetchrow(
        """
        SELECT
            AVG(cnt) AS avg_per_day,
            MIN(cnt) AS min_per_day,
            MAX(cnt) AS max_per_day
        FROM (
            SELECT date, COUNT(*) AS cnt
            FROM strike_history
            WHERE symbol = $1
            GROUP BY date
        ) sub
        """,
        symbol,
    )
    unique = await conn.fetchval(
        "SELECT COUNT(DISTINCT strike) FROM strike_history WHERE symbol = $1",
        symbol,
    )
    total = await conn.fetchval(
        "SELECT COUNT(*) FROM strike_history WHERE symbol = $1",
        symbol,
    )
    return {
        "avg_per_day": per_day["avg_per_day"],
        "min_per_day": per_day["min_per_day"],
        "max_per_day": per_day["max_per_day"],
        "unique_strikes": unique,
        "total_rows": total,
    }


async def _fetch_pcr_stats(conn: asyncpg.Connection, symbol: str) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                                          AS total_days,
            COUNT(*) FILTER (WHERE pcr_oi IS NOT NULL)        AS valid_pcr_days,
            MIN(pcr_oi)                                       AS pcr_min,
            MAX(pcr_oi)                                       AS pcr_max,
            AVG(pcr_oi)                                       AS pcr_avg,
            COUNT(*) FILTER (WHERE pcr_oi > 1.5)              AS extreme_high,
            COUNT(*) FILTER (WHERE pcr_oi < 0.5)              AS extreme_low,
            COUNT(*) FILTER (WHERE pcr_signal = 'BULLISH')    AS bullish,
            COUNT(*) FILTER (WHERE pcr_signal = 'BEARISH')    AS bearish,
            COUNT(*) FILTER (WHERE pcr_signal = 'NEUTRAL')    AS neutral
        FROM pcr_history
        WHERE symbol = $1
        """,
        symbol,
    )
    return dict(row)


async def _fetch_oi_stats(conn: asyncpg.Connection, symbol: str) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                                               AS total_days,
            COUNT(*) FILTER (WHERE total_ce_oi IS NOT NULL
                              AND total_pe_oi IS NOT NULL)         AS valid_oi_days,
            AVG(total_ce_oi)                                       AS avg_ce_oi,
            AVG(total_pe_oi)                                       AS avg_pe_oi,
            COUNT(*) FILTER (WHERE oi_change_ce IS NOT NULL
                              AND oi_change_pe IS NOT NULL)        AS oi_change_days
        FROM options_history
        WHERE symbol = $1
        """,
        symbol,
    )
    return dict(row)


async def _fetch_wall_stats(conn: asyncpg.Connection, symbol: str) -> dict:
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                                                      AS total_days,
            COUNT(*) FILTER (WHERE call_wall IS NOT NULL
                              AND put_wall IS NOT NULL)                    AS valid_wall_days,
            AVG(call_wall_distance_pct)                                   AS avg_cw_dist,
            AVG(put_wall_distance_pct)                                    AS avg_pw_dist
        FROM wall_history
        WHERE symbol = $1
        """,
        symbol,
    )
    return dict(row)


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


async def generate_report(output_path: str) -> None:
    """Main entry: connect, query, build markdown, write file."""

    print("🔌 Connecting to PostgreSQL …")

    pg_host = os.getenv("PG_HOST", "localhost")
    pg_port = int(os.getenv("PG_PORT", "5432"))
    pg_database = os.getenv("PG_DATABASE", "wealthquant")
    pg_user = os.getenv("PG_USER", "postgres")
    pg_password = os.getenv("PG_PASSWORD", "")

    try:
        conn: asyncpg.Connection = await asyncpg.connect(
            host=pg_host,
            port=pg_port,
            database=pg_database,
            user=pg_user,
            password=pg_password,
        )
    except Exception as exc:
        _write_error_report(output_path, str(exc))
        print(f"❌ Could not connect to PostgreSQL: {exc}")
        print(f"📄 Error report written to {output_path}")
        return

    print("✅ Connected.  Querying tables …")

    try:
        row_counts = await _fetch_table_row_counts(conn)
        symbols = await _fetch_symbols(conn)

        # Per-symbol data bundles
        symbol_data: dict[str, dict] = {}
        for sym in symbols:
            print(f"   📊 Processing {sym} …")
            first_date, last_date = await _fetch_date_range(conn, sym)
            actual_dates = await _fetch_actual_dates(conn, sym)
            strike = await _fetch_strike_stats(conn, sym)
            pcr = await _fetch_pcr_stats(conn, sym)
            oi = await _fetch_oi_stats(conn, sym)
            wall = await _fetch_wall_stats(conn, sym)

            if first_date and last_date:
                expected = _weekdays_between(first_date, last_date)
                actual_set = set(actual_dates)
                missing = sorted([d for d in expected if d not in actual_set])
            else:
                expected = []
                missing = []

            symbol_data[sym] = {
                "first_date": first_date,
                "last_date": last_date,
                "actual_dates": actual_dates,
                "expected_weekdays": expected,
                "missing_days": missing,
                "strike": strike,
                "pcr": pcr,
                "oi": oi,
                "wall": wall,
            }

        md = _build_markdown(row_counts, symbols, symbol_data)
    finally:
        await conn.close()

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(md)

    print(f"✅ Report written to {output_path}")


# ---------------------------------------------------------------------------
# Markdown composition
# ---------------------------------------------------------------------------


def _build_markdown(
    row_counts: dict[str, int],
    symbols: list[str],
    symbol_data: dict[str, dict],
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    def w(text: str = "") -> None:  # shortcut
        lines.append(text)

    # ------------------------------------------------------------------
    # Header
    # ------------------------------------------------------------------
    w("# 📈 WealthQuant V7.1 — Options Data Health Report")
    w()
    w(f"> **Generated:** {now}")
    w()

    total_rows = sum(row_counts.values())

    # ------------------------------------------------------------------
    # Accumulation Progress (prominent banner)
    # ------------------------------------------------------------------
    if symbols and symbol_data:
        # Use the symbol with the most collection days for the banner
        max_days = 0
        first_collection: date | None = None
        for sym, sd in symbol_data.items():
            n = len(sd["actual_dates"])
            if n > max_days:
                max_days = n
                first_collection = sd["first_date"]
        bar_min = _progress_bar(max_days, ACCUMULATION_TARGET_MIN)
        bar_max = _progress_bar(max_days, ACCUMULATION_TARGET_MAX)

        if first_collection and max_days > 0:
            days_elapsed = (date.today() - first_collection).days or 1
            rate = max_days / days_elapsed  # trading days per calendar day
            remaining_min = max(ACCUMULATION_TARGET_MIN - max_days, 0)
            remaining_max = max(ACCUMULATION_TARGET_MAX - max_days, 0)
            if rate > 0:
                eta_min = date.today() + timedelta(days=int(remaining_min / rate))
                eta_max = date.today() + timedelta(days=int(remaining_max / rate))
                eta_min_str = eta_min.strftime("%Y-%m-%d")
                eta_max_str = eta_max.strftime("%Y-%m-%d")
            else:
                eta_min_str = "—"
                eta_max_str = "—"
        else:
            eta_min_str = "—"
            eta_max_str = "—"

        w("---")
        w()
        w("## 🚀 Accumulation Progress")
        w()
        w("| Metric | Value |")
        w("|---|---|")
        w(f"| **Days Collected** | **{max_days}** |")
        w(f"| **Target (minimum)** | {ACCUMULATION_TARGET_MIN} days |")
        w(f"| **Target (recommended)** | {ACCUMULATION_TARGET_MAX} days |")
        w(f"| **Progress → 90 days** | {bar_min} |")
        w(f"| **Progress → 180 days** | {bar_max} |")
        w(f"| **Est. Completion (90d)** | {eta_min_str} |")
        w(f"| **Est. Completion (180d)** | {eta_max_str} |")
        w()
    else:
        w("---")
        w()
        w("## 🚀 Accumulation Progress")
        w()
        w("| Metric | Value |")
        w("|---|---|")
        w("| **Days Collected** | **0** |")
        w(f"| **Target (minimum)** | {ACCUMULATION_TARGET_MIN} days |")
        w(f"| **Target (recommended)** | {ACCUMULATION_TARGET_MAX} days |")
        w(f"| **Progress → 90 days** | {_progress_bar(0, ACCUMULATION_TARGET_MIN)} |")
        w(f"| **Progress → 180 days** | {_progress_bar(0, ACCUMULATION_TARGET_MAX)} |")
        w("| **Est. Completion (90d)** | — |")
        w("| **Est. Completion (180d)** | — |")
        w()

    # ------------------------------------------------------------------
    # Table Row Counts
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🗄️ Table Row Counts")
    w()
    w("| Table | Rows | Status |")
    w("|---|--:|---|")
    for table in TABLES:
        cnt = row_counts[table]
        status = "✅" if cnt > 0 else "⚠️ Empty"
        w(f"| `{table}` | {_fmt(cnt)} | {status} |")
    w(f"| **Total** | **{_fmt(total_rows)}** | |")
    w()

    if not symbols:
        w(
            "> ⚠️ **No data collected yet.** Start the options data pipeline to begin accumulating data."
        )
        w()
        w("---")
        w()
        w("*Report complete — no further sections to display.*")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Data Completeness
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 📋 Data Completeness")
    w()
    w("| Symbol | Collection Days | Date Range | Expected Weekdays | Completeness |")
    w("|---|--:|---|--:|---|")
    for sym in symbols:
        sd = symbol_data[sym]
        n_actual = len(sd["actual_dates"])
        n_expected = len(sd["expected_weekdays"])
        first = sd["first_date"].strftime("%Y-%m-%d") if sd["first_date"] else "—"
        last = sd["last_date"].strftime("%Y-%m-%d") if sd["last_date"] else "—"
        if n_expected > 0:
            pct = n_actual / n_expected * 100
            icon = "✅" if pct >= 95 else ("⚠️" if pct >= 80 else "❌")
            pct_str = f"{icon} {pct:.1f}%"
        else:
            pct_str = "—"
        w(f"| **{sym}** | {n_actual} | {first} → {last} | {n_expected} | {pct_str} |")
    w()

    # ------------------------------------------------------------------
    # Missing Days
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🕳️ Missing Days")
    w()
    any_missing = False
    for sym in symbols:
        sd = symbol_data[sym]
        missing = sd["missing_days"]
        if missing:
            any_missing = True
            w(f"### {sym} — {len(missing)} missing day(s)")
            w()
            # Show in rows of up to 7 dates
            chunks = [missing[i : i + 7] for i in range(0, len(missing), 7)]
            for chunk in chunks:
                w("  " + ", ".join(f"`{d.strftime('%Y-%m-%d')}`" for d in chunk))
            w()
    if not any_missing:
        w("> ✅ **No missing weekdays detected for any symbol.**")
        w()

    # ------------------------------------------------------------------
    # Strike Coverage
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🎯 Strike Coverage")
    w()
    w("| Symbol | Avg Strikes/Day | Min | Max | Unique Strikes | Total Rows |")
    w("|---|--:|--:|--:|--:|--:|")
    for sym in symbols:
        s = symbol_data[sym]["strike"]
        w(
            f"| **{sym}** "
            f"| {_fmt(s['avg_per_day'])} "
            f"| {_fmt(s['min_per_day'])} "
            f"| {_fmt(s['max_per_day'])} "
            f"| {_fmt(s['unique_strikes'])} "
            f"| {_fmt(s['total_rows'])} |"
        )
    w()

    # ------------------------------------------------------------------
    # PCR Coverage
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 📊 PCR Coverage")
    w()
    w(
        "| Symbol | Valid Days / Total | PCR Min | PCR Max | PCR Avg | Extreme High (>1.5) | Extreme Low (<0.5) |"
    )
    w("|---|---|--:|--:|--:|--:|--:|")
    for sym in symbols:
        p = symbol_data[sym]["pcr"]
        total = p["total_days"]
        valid = p["valid_pcr_days"]
        icon = "✅" if valid == total and total > 0 else ("⚠️" if valid > 0 else "❌")
        w(
            f"| **{sym}** "
            f"| {icon} {valid}/{total} "
            f"| {_fmt(p['pcr_min'])} "
            f"| {_fmt(p['pcr_max'])} "
            f"| {_fmt(p['pcr_avg'])} "
            f"| {_fmt(p['extreme_high'])} "
            f"| {_fmt(p['extreme_low'])} |"
        )
    w()

    # PCR Signal Distribution
    w("### PCR Signal Distribution")
    w()
    w("| Symbol | 🟢 BULLISH | 🔴 BEARISH | ⚪ NEUTRAL |")
    w("|---|--:|--:|--:|")
    for sym in symbols:
        p = symbol_data[sym]["pcr"]
        w(
            f"| **{sym}** "
            f"| {_fmt(p['bullish'])} "
            f"| {_fmt(p['bearish'])} "
            f"| {_fmt(p['neutral'])} |"
        )
    w()

    # ------------------------------------------------------------------
    # OI Coverage
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🔢 OI Coverage")
    w()
    w("| Symbol | Valid OI Days / Total | Avg CE OI | Avg PE OI | Days w/ OI Change |")
    w("|---|---|--:|--:|--:|")
    for sym in symbols:
        o = symbol_data[sym]["oi"]
        total = o["total_days"]
        valid = o["valid_oi_days"]
        icon = "✅" if valid == total and total > 0 else ("⚠️" if valid > 0 else "❌")
        w(
            f"| **{sym}** "
            f"| {icon} {valid}/{total} "
            f"| {_fmt(o['avg_ce_oi'])} "
            f"| {_fmt(o['avg_pe_oi'])} "
            f"| {_fmt(o['oi_change_days'])} |"
        )
    w()

    # ------------------------------------------------------------------
    # Wall Coverage
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🧱 Wall Coverage")
    w()
    w(
        "| Symbol | Valid Wall Days / Total | Avg Call Wall Dist (%) | Avg Put Wall Dist (%) |"
    )
    w("|---|---|--:|--:|")
    for sym in symbols:
        wl = symbol_data[sym]["wall"]
        total = wl["total_days"]
        valid = wl["valid_wall_days"]
        icon = "✅" if valid == total and total > 0 else ("⚠️" if valid > 0 else "❌")
        w(
            f"| **{sym}** "
            f"| {icon} {valid}/{total} "
            f"| {_fmt(wl['avg_cw_dist'])} "
            f"| {_fmt(wl['avg_pw_dist'])} |"
        )
    w()

    # ------------------------------------------------------------------
    # Per-Symbol Summary
    # ------------------------------------------------------------------
    w("---")
    w()
    w("## 🏷️ Per-Symbol Summary")
    w()
    for sym in symbols:
        sd = symbol_data[sym]
        n_days = len(sd["actual_dates"])
        w(f"### {sym}")
        w()
        w(f"- **Collection days:** {n_days}")
        if sd["first_date"] and sd["last_date"]:
            w(
                f"- **Range:** {sd['first_date'].strftime('%Y-%m-%d')} → {sd['last_date'].strftime('%Y-%m-%d')}"
            )
        w(f"- **Missing days:** {len(sd['missing_days'])}")
        w(f"- **Unique strikes:** {_fmt(sd['strike']['unique_strikes'])}")
        w(
            f"- **PCR valid days:** {sd['pcr']['valid_pcr_days']}/{sd['pcr']['total_days']}"
        )
        w(
            f"- **Wall valid days:** {sd['wall']['valid_wall_days']}/{sd['wall']['total_days']}"
        )
        bar = _progress_bar(n_days, ACCUMULATION_TARGET_MIN)
        w(f"- **Accumulation (→90d):** {bar}")
        w()

    # ------------------------------------------------------------------
    # Footer
    # ------------------------------------------------------------------
    w("---")
    w()
    w(f"*Report generated by `generate_health_report.py` on {now}*")
    w()

    return "\n".join(lines) + "\n"


def _write_error_report(output_path: str, error: str) -> None:
    """Write a minimal report when the database is unreachable."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = (
        "# 📈 WealthQuant V7.1 — Options Data Health Report\n"
        "\n"
        f"> **Generated:** {now}\n"
        "\n"
        "---\n"
        "\n"
        "## ❌ Database Connection Error\n"
        "\n"
        f"Could not connect to PostgreSQL:\n"
        "\n"
        f"```\n{error}\n```\n"
        "\n"
        "Please verify your `.env` configuration and that PostgreSQL is running.\n"
        "\n"
        "---\n"
        "\n"
        f"*Report generated by `generate_health_report.py` on {now}*\n"
    )
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(md)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the WealthQuant V7.1 Options Data Health Report.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output path for the Markdown report (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  WealthQuant V7.1 — Options Data Health Report Generator")
    print("=" * 60)
    print()

    asyncio.run(generate_report(args.output))


if __name__ == "__main__":
    main()
