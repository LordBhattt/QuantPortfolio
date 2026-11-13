"""Reproduce the offline data, ML evaluation, and optional model training flow."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-lstm", action="store_true")
    args = parser.parse_args()

    commands = []
    if not args.skip_download:
        commands.append([sys.executable, "backend/scripts/download_data.py", "--skip-macro"])
    commands.append([sys.executable, "backend/scripts/train_gbm_forecaster.py"])
    if not args.skip_lstm:
        commands.append([sys.executable, "backend/ml/trainer.py"])
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
