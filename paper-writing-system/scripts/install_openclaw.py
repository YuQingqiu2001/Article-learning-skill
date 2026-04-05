"""Simple installer for Openclaw/Codex skill directory.

Usage (Windows):
  python scripts/install_openclaw.py
  python scripts/install_openclaw.py --codex-home "C:\\Users\\me\\.codex"
  python scripts/install_openclaw.py --with-venv --force
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


SKILL_NAME = "paper-writing-system"
REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "agents/openai.yaml",
    "scripts/learn_papers.py",
    "scripts/openclaw_entry.py",
]


def resolve_codex_home(user_input: str = "") -> Path:
    if user_input:
        return Path(user_input).expanduser().resolve()
    env = os.getenv("CODEX_HOME", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def install_skill(codex_home: Path, force: bool = False) -> Path:
    skill_root = Path(__file__).resolve().parents[1]
    target = codex_home / "skills" / SKILL_NAME
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if not force:
            raise FileExistsError(f"Target already exists: {target}. Use --force to overwrite.")
        shutil.rmtree(target)

    shutil.copytree(skill_root, target)
    return target


def validate_install(target: Path) -> tuple[bool, list[str]]:
    missing = [f for f in REQUIRED_FILES if not (target / f).exists()]
    return len(missing) == 0, missing


def setup_venv_and_deps(target: Path) -> None:
    venv_dir = target / ".venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    if os.name == "nt":
        py = venv_dir / "Scripts" / "python.exe"
    else:
        py = venv_dir / "bin" / "python"
    subprocess.run([str(py), "-m", "pip", "install", "-r", str(target / "requirements.txt")], check=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Install paper-writing-system into Openclaw/Codex skills directory")
    p.add_argument("--codex-home", default="", help="Override CODEX_HOME path")
    p.add_argument("--force", action="store_true", help="Overwrite existing installation")
    p.add_argument("--dry-run", action="store_true", help="Print actions only")
    p.add_argument("--with-venv", action="store_true", help="Create .venv and install requirements in installed skill")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    codex_home = resolve_codex_home(args.codex_home)
    target = codex_home / "skills" / SKILL_NAME

    if args.dry_run:
        print(f"[dry-run] codex_home = {codex_home}")
        print(f"[dry-run] target = {target}")
        print("[dry-run] validate required files after install")
        if args.with_venv:
            print("[dry-run] setup .venv + pip install -r requirements.txt")
        return 0

    try:
        installed = install_skill(codex_home, force=args.force)
        ok, missing = validate_install(installed)
        if not ok:
            print(f"Install failed validation. Missing files: {missing}")
            return 3

        if args.with_venv:
            setup_venv_and_deps(installed)

        print(f"Installed skill to: {installed}")
        print("Tip: run with `python scripts/openclaw_entry.py` inside installed skill.")
        return 0
    except FileExistsError as exc:
        print(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
