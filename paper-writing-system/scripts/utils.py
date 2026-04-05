"""Utility helpers for paper-writing-system v0.1 skeleton."""
from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT_DIR = r"D:\sci文献数据" if platform.system() == "Windows" else str(Path.home() / "sci_papers")


@dataclass
class PDFFile:
    path: Path
    modified_time: datetime
    file_hash: str


def ensure_runtime_structure(base_dir: Path) -> None:
    """Ensure runtime folders/files exist."""
    (base_dir / "runtime" / "memory").mkdir(parents=True, exist_ok=True)
    (base_dir / "runtime" / "skills" / "generated_examples").mkdir(parents=True, exist_ok=True)
    processed = base_dir / "runtime" / "processed_files.json"
    if not processed.exists():
        processed.write_text("[]\n", encoding="utf-8")


def file_sha256(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash for stable dedup check."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def scan_recent_pdfs(input_dir: Path, days: int) -> list[PDFFile]:
    """Scan recent PDFs by modified time."""
    if not input_dir.exists():
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent: list[PDFFile] = []
    for pdf in input_dir.rglob("*.pdf"):
        try:
            ts = datetime.fromtimestamp(pdf.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if ts >= cutoff:
            try:
                fhash = file_sha256(pdf)
            except OSError:
                continue
            recent.append(PDFFile(path=pdf, modified_time=ts, file_hash=fhash))
    return sorted(recent, key=lambda x: x.modified_time, reverse=True)


def load_json(file_path: Path, default: Any) -> Any:
    if not file_path.exists():
        return default
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default


def save_json(file_path: Path, payload: Any) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def normalize_windows_path(path: Path | str) -> str:
    """Normalize output path for Windows-style readability."""
    return str(Path(path)).replace("/", "\\")
