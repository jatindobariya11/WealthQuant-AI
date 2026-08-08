import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("platform_monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("platform_monitor")

backend_dir = Path(__file__).parent.resolve()
project_dir = backend_dir.parent.resolve()
frontend_dir = project_dir / "frontend"

pg_local_dir = backend_dir / "pg_local"
pg_ctl = pg_local_dir / "pgsql" / "bin" / "pg_ctl.exe"
pg_data = pg_local_dir / "data"
pg_log = pg_local_dir / "pg.log"
pid_file = pg_data / "postmaster.pid"

python_exe = backend_dir / ".venv" / "Scripts" / "python.exe"


def is_port_open(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except:
            return False


def clean_stale_pid():
    if pid_file.exists():
        logger.info(f"Found postmaster.pid at {pid_file}. Verifying process...")
        try:
            with open(pid_file) as f:
                lines = f.readlines()
            if lines:
                pid_val = int(lines[0].strip())
                logger.info(f"Checking if process {pid_val} is running...")
                import psutil

                if psutil.pid_exists(pid_val):
                    proc = psutil.Process(pid_val)
                    if "postgres" in proc.name().lower():
                        logger.info(f"PostgreSQL is active on PID {pid_val}.")
                        return True
                logger.warning(
                    f"Process {pid_val} is dead or not PostgreSQL. Removing stale PID file."
                )
                if pid_file.exists():
                    pid_file.unlink()
                    logger.info("Stale PID file deleted.")
        except Exception as e:
            logger.error(f"Error checking PID file: {e}. Removing file.")
            try:
                pid_file.unlink()
            except:
                pass
    return False


def start_postgres():
    if is_port_open(5432):
        logger.info("PostgreSQL port 5432 is already open.")
        return

    clean_stale_pid()
    logger.info("Starting PostgreSQL...")
    cmd = [str(pg_ctl), "-D", str(pg_data), "-l", str(pg_log), "start"]
    subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

    for i in range(15):
        time.sleep(1)
        if is_port_open(5432):
            logger.info("PostgreSQL is listening on port 5432.")
            return
    logger.error("PostgreSQL failed to start within 15 seconds.")


def main_loop():
    logger.info("Starting WealthQuant Platform Monitor...")

    # 1. Start Postgres
    start_postgres()

    # Process handles
    api_proc = None
    react_proc = None
    ollama_proc = None

    while True:
        try:
            # Verify Postgres is still listening
            if not is_port_open(5432):
                logger.warning("PostgreSQL port 5432 is closed! Restarting...")
                start_postgres()

            # Verify mock Ollama (Qwen Analyst) on port 11434
            if not is_port_open(11434):
                if ollama_proc:
                    logger.warning(
                        "Mock Ollama process exited or port closed. Restarting..."
                    )
                    try:
                        ollama_proc.terminate()
                    except:
                        pass
                logger.info("Launching Mock Ollama Server (Qwen)...")
                ollama_proc = subprocess.Popen(
                    [str(python_exe), "mock_ollama.py"],
                    cwd=str(backend_dir),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            # Verify FastAPI on port 8000
            if not is_port_open(8000):
                if api_proc:
                    logger.warning(
                        "FastAPI process exited or port closed. Restarting..."
                    )
                    try:
                        api_proc.terminate()
                    except:
                        pass
                logger.info("Launching FastAPI Backend...")
                api_proc = subprocess.Popen(
                    [
                        str(python_exe),
                        "-m",
                        "uvicorn",
                        "main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        "8000",
                    ],
                    cwd=str(backend_dir),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            # Verify React Frontend on port 3000
            if not is_port_open(3000):
                if react_proc:
                    logger.warning("React process exited or port closed. Restarting...")
                    try:
                        react_proc.terminate()
                    except:
                        pass
                logger.info("Launching React Frontend...")
                react_proc = subprocess.Popen(
                    ["npm", "start"],
                    cwd=str(frontend_dir),
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )

            # Log statuses
            logger.info(
                f"Status check - Postgres (5432): {'OPEN' if is_port_open(5432) else 'CLOSED'} | "
                f"Ollama (11434): {'OPEN' if is_port_open(11434) else 'CLOSED'} | "
                f"FastAPI (8000): {'OPEN' if is_port_open(8000) else 'CLOSED'} | "
                f"React (3000): {'OPEN' if is_port_open(3000) else 'CLOSED'}"
            )

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")

        time.sleep(10)


if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        logger.info("Monitor interrupted. Exiting.")
