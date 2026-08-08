import asyncio
import json
import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline.db import pipeline_db


def get_process_memory(name_filter):
    try:
        import subprocess

        # Get memory in KB using tasklist
        cmd = f'tasklist /FI "IMAGENAME eq {name_filter}" /FO CSV /NH'
        out = subprocess.check_output(cmd, shell=True).decode("utf-8", errors="ignore")
        total_kb = 0
        pids = []
        for line in out.strip().split("\n"):
            if not line.strip():
                continue
            parts = [p.strip('"') for p in line.split(",")]
            if len(parts) >= 5:
                mem_str = parts[4].replace(" K", "").replace(",", "").replace(".", "")
                try:
                    total_kb += int(mem_str)
                    pids.append(parts[1])
                except ValueError:
                    pass
        return round(total_kb / 1024.0, 2), pids  # Return in MB
    except Exception:
        return 0.0, []


def get_system_perf():
    import subprocess

    perf = {
        "cpu_percent": 0.0,
        "ram_percent": 0.0,
        "ram_total_gb": 0.0,
        "ram_used_gb": 0.0,
    }
    try:
        # Get CPU usage via wmic
        cpu_out = (
            subprocess.check_output("wmic cpu get LoadPercentage /value", shell=True)
            .decode()
            .strip()
        )
        if "LoadPercentage=" in cpu_out:
            perf["cpu_percent"] = float(cpu_out.split("=")[1])

        # Get RAM usage via systeminfo or powershell
        ram_out = subprocess.check_output(
            'powershell -Command "$mem = Get-CimInstance Win32_OperatingSystem; [PSCustomObject]@{Total=Round($mem.TotalVisibleMemorySize/1GB, 2); Free=Round($mem.FreePhysicalMemory/1GB, 2)}" | ConvertTo-Json',
            shell=True,
        ).decode()
        ram_data = json.loads(ram_out)
        total = ram_data.get("Total", 16.0)
        free = ram_data.get("Free", 8.0)
        used = total - free
        perf["ram_total_gb"] = total
        perf["ram_used_gb"] = round(used, 2)
        perf["ram_percent"] = round((used / total) * 100.0, 1)
    except Exception:
        pass
    return perf


async def main():
    connected = await pipeline_db.init_pool()
    db_size = "Unknown"
    if connected:
        async with pipeline_db.pool.acquire() as conn:
            db_size = await conn.fetchval(
                "SELECT pg_size_pretty(pg_database_size(current_database()))"
            )
        await pipeline_db.close()

    sys_perf = get_system_perf()
    pg_mem, pg_pids = get_process_memory("postgres.exe")
    py_mem, py_pids = get_process_memory("python.exe")

    # Measure prediction latency via API call
    import urllib.request

    t0 = time.time()
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:8000/api/pipeline/probability/NIFTY?interval=15m",
            timeout=10,
        )
        pred_latency = round((time.time() - t0), 3)
    except Exception:
        pred_latency = 0.0

    perf_report = {
        "cpu_usage_pct": sys_perf["cpu_percent"],
        "ram_usage_pct": sys_perf["ram_percent"],
        "ram_used_gb": sys_perf["ram_used_gb"],
        "ram_total_gb": sys_perf["ram_total_gb"],
        "gpu_usage": "N/A (CPU execution active)",
        "postgres_memory_mb": pg_mem,
        "postgres_processes": len(pg_pids),
        "backend_memory_mb": py_mem,
        "prediction_latency_seconds": pred_latency,
        "database_size": db_size,
    }

    print(json.dumps(perf_report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
