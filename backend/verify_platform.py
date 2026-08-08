import asyncio
import os
import socket
import subprocess
import sys

try:
    import psutil
except ImportError:
    psutil = None
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("startup")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Hack to make imports work from backend dir
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from dotenv import load_dotenv

load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), ".env")))

from pipeline.db import pipeline_db
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.scheduler import scheduler as wq_scheduler


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except:
            return False


async def main():
    dashboard = [
        "# WealthQuant Platform STARTUP DASHBOARD",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
        "## 1. System Health (Services)",
    ]

    # Check Ports
    pg_running = is_port_open(5432)
    api_running = is_port_open(8000)
    react_running = is_port_open(3000)

    dashboard.append(
        f"- PostgreSQL (5432): {'🟢 RUNNING' if pg_running else '🔴 OFFLINE'}"
    )
    dashboard.append(
        f"- FastAPI (8000): {'🟢 RUNNING' if api_running else '🔴 OFFLINE'}"
    )
    dashboard.append(
        f"- React (3000): {'🟢 RUNNING' if react_running else '🔴 OFFLINE'}"
    )

    if not pg_running:
        logger.info("Starting PostgreSQL...")
        pg_ctl = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__), "pg_local", "pgsql", "bin", "pg_ctl.exe"
            )
        )
        pg_data = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "pg_local", "data")
        )
        pg_log = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "pg_local", "pg.log")
        )
        subprocess.Popen(
            [pg_ctl, "-D", pg_data, "-l", pg_log, "start"], creationflags=0x00000008
        )
    if not api_running:
        logger.info("Starting FastAPI...")
        python_exe = os.path.abspath(
            os.path.join(os.path.dirname(__file__), ".venv", "Scripts", "python.exe")
        )
        subprocess.Popen(
            [
                python_exe,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ],
            cwd=os.path.abspath(os.path.dirname(__file__)),
            creationflags=0x00000008,
        )
    if not react_running:
        logger.info("Starting React...")
        subprocess.Popen(
            ["npm", "start"],
            cwd=os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "frontend")
            ),
            shell=True,
            creationflags=0x00000008,
        )

    # Wait for services to be ready before continuing
    logger.info("Waiting 15 seconds for services to initialize...")
    await asyncio.sleep(15)

    dashboard.append("")
    dashboard.append("## 2. Database Health")
    try:
        await pipeline_db.init_pool()
        if pipeline_db.is_connected:
            async with pipeline_db.pool.acquire() as conn:
                tables = await conn.fetch(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema'"
                )
                total_tables = len(tables)
                total_rows = 0
                today_rows = 0
                largest_table = ("", 0)

                for t in tables:
                    tbl = t["tablename"]
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {tbl}")
                    total_rows += count
                    if count > largest_table[1]:
                        largest_table = (tbl, count)

                    # Check for today's rows if timestamp exists
                    try:
                        cols = [
                            r["column_name"]
                            for r in await conn.fetch(
                                f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tbl}'"
                            )
                        ]
                        date_col = next(
                            (
                                c
                                for c in cols
                                if c in ["date", "timestamp", "created_at"]
                            ),
                            None,
                        )
                        if date_col:
                            t_rows = await conn.fetchval(
                                f"SELECT COUNT(*) FROM {tbl} WHERE {date_col} >= CURRENT_DATE"
                            )
                            today_rows += t_rows
                    except Exception:
                        pass

                dashboard.append(f"- **Total Tables:** {total_tables}")
                dashboard.append(f"- **Total Rows:** {total_rows:,}")
                dashboard.append(f"- **Today's New Rows:** {today_rows:,}")
                dashboard.append(
                    f"- **Largest Table:** {largest_table[0]} ({largest_table[1]:,} rows)"
                )
                dashboard.append("- **Connection Status:** 🟢 HEALTHY")
        else:
            dashboard.append("- **Connection Status:** 🔴 FAILED TO CONNECT")
    except Exception as db_err:
        dashboard.append(f"- **Connection Status:** 🔴 FAILED TO CONNECT ({db_err})")

    dashboard.append("")
    dashboard.append("## 3 & 4 & 5. Scheduler & Market Data")
    try:
        if hasattr(wq_scheduler, "is_running"):
            sched_running = wq_scheduler.is_running()
        else:
            sched_running = True  # Assume running if no method
        dashboard.append(
            f"- **Scheduler Active:** {'🟢 YES' if sched_running else '🔴 NO'}"
        )

        # Check market data rows
        if pipeline_db.is_connected:
            async with pipeline_db.pool.acquire() as conn:
                missing = 0
                try:
                    missing = await conn.fetchval(
                        "SELECT COUNT(*) FROM options_intelligence WHERE pcr IS NULL"
                    )
                except:
                    pass
                dashboard.append(f"- **Options Feed Missing/NULL Rows:** {missing}")

                try:
                    last_ohlcv = await conn.fetchval(
                        "SELECT MAX(timestamp) FROM ohlcv_history WHERE symbol = 'NIFTY'"
                    )
                    dashboard.append(f"- **Last NIFTY OHLCV:** {last_ohlcv}")
                except:
                    pass
    except Exception as sch_err:
        dashboard.append(f"- **Scheduler Check Failed:** {sch_err}")

    dashboard.append("")
    dashboard.append("## 6 & 7. Live Prediction & Explainability (Part 8)")
    try:
        orchestrator = PipelineOrchestrator()
        result = await orchestrator.run("NIFTY", skip_llm=True)
        dashboard.append("- **Symbol:** NIFTY")
        dashboard.append(f"- **Timestamp:** {result.timestamp}")
        dashboard.append(
            f"- **Regime:** {result.regime.current_regime} ({result.regime.regime_confidence * 100:.1f}% conf)"
        )
        dashboard.append(
            f"- **Signal:** {result.probabilities.signal} (Confidence: {result.probabilities.signal_confidence * 100:.1f}%)"
        )
        dashboard.append(
            f"- **Expected Return:** {result.probabilities.expected_return * 100:.2f}%"
        )
        dashboard.append(
            f"- **Bayesian Dominant Model:** {result.fusion.dominant_model}"
        )
        dashboard.append("- 🟢 Prediction Engine Intact")
    except Exception as pred_err:
        dashboard.append(f"- 🔴 Prediction Engine Failed: {pred_err}")

    dashboard.append("")
    dashboard.append("## 9. Performance (Hardware & Latency)")
    if psutil:
        dashboard.append(f"- **CPU Usage:** {psutil.cpu_percent()}%")
        dashboard.append(f"- **RAM Usage:** {psutil.virtual_memory().percent}%")
        process = psutil.Process(os.getpid())
        dashboard.append(
            f"- **Python Memory:** {process.memory_info().rss / (1024 * 1024):.2f} MB"
        )
    else:
        dashboard.append("- **CPU Usage:** N/A (psutil not installed)")
        dashboard.append("- **RAM Usage:** N/A")

    output_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "STARTUP_DASHBOARD.md")
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(dashboard))
    print(f"Generated {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
