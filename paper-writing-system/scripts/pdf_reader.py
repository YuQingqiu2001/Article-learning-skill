"""Robust PDF reading helpers for complex journal layouts.

Priority:
1) PyMuPDF (fitz) block extraction for multi-column Nature-like layouts
2) pypdf plain extraction fallback
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ModuleNotFoundError:  # pragma: no cover
    fitz = None

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # pragma: no cover
    PdfReader = None


SECTION_KEYS = ["abstract", "introduction", "methods", "materials and methods", "results", "discussion", "conclusion"]


def extract_pdf_content(pdf_path: Path, max_pages: int = 30) -> tuple[str, list[str], dict[str, str], dict[str, Any]]:
    """Extract text+sections with best available backend."""
    if fitz is not None:
        try:
            text, headers, section_map = _extract_with_pymupdf(pdf_path, max_pages=max_pages)
            return text, headers, section_map, {"backend": "pymupdf"}
        except Exception:  # noqa: BLE001
            pass

    if PdfReader is None:
        raise RuntimeError("No PDF backend available. Install pymupdf or pypdf.")

    text, headers, section_map = _extract_with_pypdf(pdf_path, max_pages=max_pages)
    return text, headers, section_map, {"backend": "pypdf"}


def _extract_with_pymupdf(pdf_path: Path, max_pages: int = 30) -> tuple[str, list[str], dict[str, str]]:
    doc = fitz.open(str(pdf_path))
    lines: list[str] = []

    for page in doc[:max_pages]:
        blocks = page.get_text("blocks")
        # blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks_sorted = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))
        for b in blocks_sorted:
            txt = (b[4] or "").strip()
            if not txt:
                continue
            for ln in txt.splitlines():
                line = ln.strip()
                if line:
                    lines.append(line)

    return _sectionize_lines(lines)


def _extract_with_pypdf(pdf_path: Path, max_pages: int = 30) -> tuple[str, list[str], dict[str, str]]:
    reader = PdfReader(str(pdf_path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:max_pages])
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    return _sectionize_lines(lines)


def _sectionize_lines(lines: list[str]) -> tuple[str, list[str], dict[str, str]]:
    headers: list[str] = []
    section_map: dict[str, list[str]] = {"body": []}
    current = "body"

    for raw in lines:
        low = raw.lower().strip()
        if len(raw) <= 90 and any(k == low or low.startswith(k + " ") for k in SECTION_KEYS):
            current = "methods" if low.startswith("materials and methods") else low.split()[0]
            headers.append(raw)
            section_map.setdefault(current, [])
            continue
        section_map.setdefault(current, []).append(raw)

    text = "\n".join(lines)
    return text, headers, {k: "\n".join(v) for k, v in section_map.items()}
