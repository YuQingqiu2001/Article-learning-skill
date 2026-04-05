"""Openclaw-friendly entrypoint wrapper.

This wrapper converts Openclaw env vars into CLI args for `learn_papers.py`.
It allows installing this folder as a skill and invoking it with minimal setup.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def build_args_from_env() -> list[str]:
    from utils import DEFAULT_INPUT_DIR
    input_dir = os.getenv("OPENCLAW_INPUT_DIR", DEFAULT_INPUT_DIR)
    days = os.getenv("OPENCLAW_DAYS", "1")
    dry_run = os.getenv("OPENCLAW_DRY_RUN", "0") == "1"
    force = os.getenv("OPENCLAW_FORCE", "0") == "1"
    verbose = os.getenv("OPENCLAW_VERBOSE", "1") == "1"
    max_files = os.getenv("OPENCLAW_MAX_FILES", "0")
    stop_on_bias = os.getenv("OPENCLAW_STOP_ON_BIAS", "0") == "1"
    feedback_file = os.getenv("OPENCLAW_FEEDBACK_FILE", "")
    max_pages = os.getenv("OPENCLAW_MAX_PAGES", "30")

    args = [
        "--input-dir",
        input_dir,
        "--days",
        days,
        "--max-files",
        max_files,
        "--max-pages",
        max_pages,
    ]
    if dry_run:
        args.append("--dry-run")
    if force:
        args.append("--force")
    if verbose:
        args.append("--verbose")
    if stop_on_bias:
        args.append("--stop-on-bias")
    if feedback_file:
        args.extend(["--feedback-file", feedback_file])
    return args


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    learn_script = skill_root / "scripts" / "learn_papers.py"
    cmd = [sys.executable, str(learn_script), *build_args_from_env()]
    completed = subprocess.run(cmd, cwd=skill_root, check=False)
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
