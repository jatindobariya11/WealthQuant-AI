import importlib.metadata
import os
import sys
from datetime import datetime

import psycopg2


def run_preflight_checks():
    startup_report = []
    dep_report = []
    critical_failure = False

    # 1. Python Version
    py_version = sys.version_info
    py_ver_str = f"{py_version.major}.{py_version.minor}.{py_version.micro}"
    if py_version.major < 3 or (py_version.major == 3 and py_version.minor < 10):
        startup_report.append(
            f"❌ Python Version: {py_ver_str} (Requires >= 3.10) - CRITICAL"
        )
        critical_failure = True
    else:
        startup_report.append(f"✅ Python Version: {py_ver_str}")

    # 2. Virtual Environment
    is_venv = sys.prefix != sys.base_prefix
    if not is_venv:
        startup_report.append("⚠️ Virtual Environment: Not Active - Warning")
        # critical_failure = True
    else:
        startup_report.append(f"✅ Virtual Environment: Active ({sys.prefix})")

    # 3. Dependencies
    dep_report.append("# DEPENDENCY REPORT\n")
    dep_report.append(f"Generated at: {datetime.now().isoformat()}\n")

    req_path = os.path.join(os.path.dirname(__file__), "requirements.txt")
    missing_deps = []
    if os.path.exists(req_path):
        with open(req_path, encoding="utf-16", errors="ignore") as f:
            try:
                lines = f.readlines()
            except:
                with open(req_path, encoding="utf-8", errors="ignore") as f2:
                    lines = f2.readlines()

        for line in lines:
            line = line.strip().replace("\ufeff", "")
            if not line or line.startswith("#"):
                continue
            # Basic parsing of requirement line (e.g. pandas==2.3.3)
            pkg_name = (
                line.split("=")[0].split(">")[0].split("<")[0].split("~")[0].strip()
            )
            # mapping some common mismatches
            import_name = pkg_name.lower().replace("-", "_")
            if pkg_name.lower() == "beautifulsoup4":
                import_name = "bs4"
            if pkg_name.lower() == "pyjwt":
                import_name = "jwt"

            try:
                # We just check if it's installed in the env metadata
                importlib.metadata.version(pkg_name)
                dep_report.append(f"- ✅ {pkg_name} is installed.")
            except importlib.metadata.PackageNotFoundError:
                try:
                    # Fallback to try importing
                    __import__(import_name)
                    dep_report.append(
                        f"- ✅ {pkg_name} is installed (verified via import)."
                    )
                except ImportError:
                    missing_deps.append(pkg_name)
                    dep_report.append(f"- ❌ {pkg_name} is MISSING.")
    else:
        startup_report.append("❌ requirements.txt not found! - CRITICAL")
        critical_failure = True

    if missing_deps:
        startup_report.append(
            f"❌ Dependencies: Missing {len(missing_deps)} packages - CRITICAL"
        )
        critical_failure = True
    else:
        startup_report.append(
            f"✅ Dependencies: All {len(lines) if 'lines' in locals() else 0} packages installed."
        )

    # 4. Environment Variables
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        startup_report.append("❌ Environment: .env file missing - CRITICAL")
        critical_failure = True
    else:
        startup_report.append("✅ Environment: .env file found.")

    # 5. PostgreSQL (Non-critical, triggers degraded mode)
    # Read from .env manually if needed
    import dotenv

    dotenv.load_dotenv(env_path)
    pg_host = os.getenv("PG_HOST", "127.0.0.1")
    pg_port = int(os.getenv("PG_PORT", 5432))
    pg_user = os.getenv("PG_USER", "wealthquant")
    pg_password = os.getenv("PG_PASSWORD", "wealthquant")
    pg_db = os.getenv("PG_DATABASE", "wealthquant")

    try:
        conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            user=pg_user,
            password=pg_password,
            dbname=pg_db,
            connect_timeout=2,
        )
        conn.close()
        startup_report.append(f"✅ PostgreSQL: Connected ({pg_host}:{pg_port})")
    except Exception as e:
        startup_report.append(
            f"⚠️ PostgreSQL: Unavailable - Entering DEGRADED MODE (Error: {str(e).splitlines()[0]})"
        )

    # Generate Reports
    root_dir = os.path.dirname(os.path.dirname(__file__))

    with open(
        os.path.join(root_dir, "DEPENDENCY_REPORT.md"), "w", encoding="utf-8"
    ) as f:
        f.write("\n".join(dep_report))

    startup_content = "# SYSTEM STARTUP REPORT\n\n"
    startup_content += f"Generated at: {datetime.now().isoformat()}\n\n"
    startup_content += "\n".join(startup_report)
    startup_content += "\n\nSTATUS: " + ("FAILED" if critical_failure else "PASSED")

    with open(
        os.path.join(root_dir, "SYSTEM_STARTUP_REPORT.md"), "w", encoding="utf-8"
    ) as f:
        f.write(startup_content)

    if critical_failure:
        print("=====================================================")
        print("CRITICAL STARTUP FAILURE DETECTED")
        print("Please check SYSTEM_STARTUP_REPORT.md for details.")
        print("=====================================================")
        sys.exit(1)


if __name__ == "__main__":
    run_preflight_checks()
