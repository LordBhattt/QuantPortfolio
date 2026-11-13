"""Start the local demo stack with SQLite, memory cache, and the frontend."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    env = os.environ.copy()
    env.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./quantportfolio.db")
    env.setdefault("REDIS_URL", "redis://127.0.0.1:6379")

    subprocess.run(
        [sys.executable, str(ROOT / "backend" / "scripts" / "seed_demo_portfolio.py")],
        cwd=ROOT,
        env=env,
        check=True,
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app", "--port", "8000"],
            cwd=ROOT,
            env=env,
        ),
        subprocess.Popen(
            ["npm.cmd" if sys.platform == "win32" else "npm", "run", "dev", "--", "--host", "127.0.0.1"],
            cwd=ROOT / "frontend",
            env=env,
        ),
    ]
    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGTERM)


if __name__ == "__main__":
    main()
