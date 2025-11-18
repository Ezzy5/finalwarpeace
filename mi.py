#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
from pathlib import Path

# --------- CONFIG (edit if needed) ----------
# If your Flask app entry point is different, change this:
FLASK_APP = os.environ.get("FLASK_APP", "wsgi.py")
# Optional: set your environment (uncomment if desired)
# os.environ["FLASK_ENV"] = "development"
# os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/dbname"
# -------------------------------------------

ROOT = Path(__file__).resolve().parent
MIGRATIONS_DIR = ROOT / "migrations"

def run_cmd(cmd, env=None, cwd=None):
    """Run a command, stream output, and fail fast on errors."""
    print(f"\n$ {' '.join(cmd)}")
    process = subprocess.Popen(
        cmd,
        cwd=cwd or ROOT,
        env=env or os.environ.copy(),
        stdout=sys.stdout,
        stderr=sys.stderr,
        text=True
    )
    ret = process.wait()
    if ret != 0:
        raise SystemExit(ret)

def ensure_flask_app_env():
    # Ensure FLASK_APP is set (to e.g. wsgi.py)
    env = os.environ
    if "FLASK_APP" not in env:
        env["FLASK_APP"] = FLASK_APP
        print(f"Set FLASK_APP={env['FLASK_APP']}")
    else:
        print(f"Using FLASK_APP={env['FLASK_APP']}")
    return env

def flask_cmd(*args, env=None):
    """Call `python -m flask ...` to avoid PATH/venv issues."""
    interpreter = sys.executable or "python"
    cmd = [interpreter, "-m", "flask", *args]
    run_cmd(cmd, env=env)

def main():
    env = ensure_flask_app_env()

    # 1) flask db init (only if needed)
    if MIGRATIONS_DIR.exists() and any(MIGRATIONS_DIR.iterdir()):
        print("migrations/ already exists — skipping `flask db init`.")
    else:
        print("Running `flask db init`…")
        flask_cmd("db", "init", env=env)

    # 2) flask db migrate -m " init "
    print('Running `flask db migrate -m " init "`…')
    flask_cmd("db", "migrate", "-m", " init ", env=env)

    # 3) flask db upgrade
    print("Running `flask db upgrade`…")
    flask_cmd("db", "upgrade", env=env)

    # 4) py admin.py  (use current interpreter for portability)
    admin_path = ROOT / "admin.py"
    if admin_path.exists():
        print("Running `admin.py`…")
        run_cmd([sys.executable, str(admin_path)])
    else:
        print("Skipped: admin.py not found in project root.")

    # 5) py wsgi.py (keep server running)
    wsgi_path = ROOT / "wsgi.py"
    if wsgi_path.exists():
        print("Starting `wsgi.py` (this will stay running)…")
        # Use exec-like behavior so Ctrl+C stops the server cleanly.
        os.execv(sys.executable, [sys.executable, str(wsgi_path)])
    else:
        print("wsgi.py not found. Nothing to run. Exiting.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except SystemExit as e:
        # propagate subprocess exit codes
        raise
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
