"""Manual entrypoint for paper-writing-system v0.1 skeleton."""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ModuleNotFoundError:  # optional until real PDF processing
    PdfReader = None

from knowledge_extractor import extract_knowledge
from learning_engine import PatternCandidate, extract_focus_items, load_learning_state, save_learning_state, update_learning_state
from output_writer import append_unique_bullets, write_daily_memory, write_evolution_log, write_generated_examples
from parser_article import parse_article_structure
from parser_review import parse_review_structure
from pattern_extractor import (
    abstract_patterns,
    results_logic_patterns,
    review_structure_patterns,
    scientific_phrases,
)
from pdf_classifier import classify_paper
from utils import (
    DEFAULT_INPUT_DIR,
    ensure_runtime_structure,
    load_json,
    normalize_windows_path,
    save_json,
    scan_recent_pdfs,
    today_str,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Learn recent papers and extract writing skills.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR, help="Input PDF directory")
    parser.add_argument("--days", type=int, default=1, help="Recent days window")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, skip core skill file writing")
    parser.add_argument("--force", action="store_true", help="Ignore processed index and reprocess files")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s: %(message)s")


def extract_text_and_sections(pdf_path: Path) -> tuple[str, list[str], dict[str, str]]:
    """Extract plain text and rough section map from PDF.

    TODO: switch to richer parser with layout-aware section detection.
    """
    if PdfReader is None:
        raise RuntimeError("pypdf is required for PDF text extraction. Install requirements.txt first.")

    reader = PdfReader(str(pdf_path))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:20])

    headers: list[str] = []
    section_map: dict[str, str] = {}
    keys = ["abstract", "introduction", "methods", "materials and methods", "results", "discussion", "conclusion"]

    current = "body"
    bucket: dict[str, list[str]] = {current: []}

    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        low = clean.lower()
        if len(clean) <= 80 and any(k == low or low.startswith(k + " ") for k in keys):
            current = "methods" if low.startswith("materials and methods") else low.split()[0]
            headers.append(clean)
            bucket.setdefault(current, [])
            continue
        bucket.setdefault(current, []).append(clean)

    for k, lines in bucket.items():
        section_map[k] = "\n".join(lines)

    return text, headers, section_map


def quality_flag(text: str, section_map: dict[str, str]) -> str:
    length = len(text.strip())
    has_core = sum(1 for k in ["abstract", "introduction", "methods", "results", "discussion"] if section_map.get(k))
    if length < 1500 or has_core < 2:
        return "low"
    if length < 5000 or has_core < 4:
        return "medium"
    return "high"


def to_candidates(analysis: dict[str, Any]) -> list[PatternCandidate]:
    out: list[PatternCandidate] = []
    source = analysis["file_name"]

    for item in analysis.get("patterns", {}).get("abstract_patterns", []):
        out.append(
            PatternCandidate(
                category="abstract_patterns",
                text=item["pattern"],
                source=source,
                confidence=item["confidence"],
                paper_type=analysis["paper_type"],
                quality_flag=analysis["quality_flag"],
            )
        )
    for item in analysis.get("patterns", {}).get("results_logic_patterns", []):
        out.append(
            PatternCandidate(
                category="results_logic_patterns",
                text=item["pattern"],
                source=source,
                confidence=item["confidence"],
                paper_type=analysis["paper_type"],
                quality_flag=analysis["quality_flag"],
            )
        )
    for item in analysis.get("patterns", {}).get("review_structure_patterns", []):
        out.append(
            PatternCandidate(
                category="review_structures",
                text=item["pattern"],
                source=source,
                confidence=item["confidence"],
                paper_type=analysis["paper_type"],
                quality_flag=analysis["quality_flag"],
            )
        )
    return out


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    base_dir = Path(__file__).resolve().parents[1]
    ensure_runtime_structure(base_dir)

    processed_path = base_dir / "runtime" / "processed_files.json"
    processed_records: list[dict[str, Any]] = load_json(processed_path, default=[])
    processed_index = {(r.get("file_path"), r.get("file_hash")) for r in processed_records}

    pdfs = scan_recent_pdfs(Path(args.input_dir), args.days)
    logging.info("Found %s recent PDF(s).", len(pdfs))

    analyses: list[dict[str, Any]] = []
    date_str = today_str()

    for pdf in pdfs:
        key = (normalize_windows_path(pdf.path), pdf.file_hash)
        if not args.force and key in processed_index:
            logging.debug("Skip already processed: %s", pdf.path)
            continue

        try:
            text, headers, sections = extract_text_and_sections(pdf.path)
            cls = classify_paper(pdf.path.name, text, headers)
            qf = quality_flag(text, sections)

            parsed: dict[str, Any]
            if cls.paper_type == "article":
                parsed = parse_article_structure(text, sections)
            elif cls.paper_type == "review":
                parsed = parse_review_structure(text, sections, headers)
            else:
                parsed = {"sections": {k: sections.get(k, "")[:800] for k in ["abstract", "introduction", "results", "discussion"]}}

            analysis = {
                "file_name": pdf.path.name,
                "file_path": normalize_windows_path(pdf.path),
                "modified_time": pdf.modified_time.isoformat(),
                "file_hash": pdf.file_hash,
                "processed_date": date_str,
                "paper_type": cls.paper_type,
                "quality_flag": qf,
                "status": "ok",
                "detected_sections": list(parsed.get("sections", {}).keys()),
                "parsed": parsed,
                "patterns": {
                    "abstract_patterns": abstract_patterns({"paper_type": cls.paper_type, "parsed": parsed}),
                    "results_logic_patterns": results_logic_patterns({"paper_type": cls.paper_type, "parsed": parsed}),
                    "review_structure_patterns": review_structure_patterns({"paper_type": cls.paper_type, "parsed": parsed}),
                    "scientific_phrases": scientific_phrases({"paper_type": cls.paper_type}),
                },
                "knowledge": extract_knowledge(text, cls.paper_type),
            }
            analysis["pattern_brief"] = [p.get("pattern", p.get("phrase", "")) for group in analysis["patterns"].values() for p in group][:4]
            analyses.append(analysis)
        except Exception as exc:  # noqa: BLE001
            logging.exception("Failed processing %s: %s", pdf.path, exc)
            analyses.append(
                {
                    "file_name": pdf.path.name,
                    "file_path": normalize_windows_path(pdf.path),
                    "modified_time": pdf.modified_time.isoformat(),
                    "file_hash": pdf.file_hash,
                    "processed_date": date_str,
                    "paper_type": "uncertain",
                    "quality_flag": "low",
                    "status": "failed_extract",
                    "detected_sections": [],
                    "pattern_brief": [],
                    "parsed": {},
                    "patterns": {},
                    "knowledge": [],
                }
            )

    memory_file = base_dir / "runtime" / "memory" / f"{date_str}.md"
    if not analyses:
        write_daily_memory(memory_file, date_str, analyses, message="无新增文献")
        logging.info("No new files to process.")
        return 0

    write_daily_memory(memory_file, date_str, analyses)

    if not args.dry_run:
        # 仅沉淀高质量且非失败结果
        valid = [a for a in analyses if a["status"] == "ok" and a["quality_flag"] != "low"]

        abs_bullets = []
        res_bullets = []
        dis_bullets = []
        rev_bullets = []
        sci_bullets = []

        # Human-like evolution state: repeated exposure boosts confidence.
        learning_state_path = base_dir / "runtime" / "skills" / "learning_state.json"
        state = load_learning_state(learning_state_path)
        daily_candidates: list[PatternCandidate] = []

        for a in valid:
            src = a["file_name"]
            daily_candidates.extend(to_candidates(a))

            for item in a["patterns"].get("abstract_patterns", []):
                abs_bullets.append(f"[{item['confidence']}] {item['pattern']} (source: {src})")
            for item in a["patterns"].get("results_logic_patterns", []):
                res_bullets.append(f"[{item['confidence']}] {item['pattern']} (source: {src})")
            if a["paper_type"] == "article":
                dis_bullets.append(f"[medium] result -> mechanism -> literature -> inference (source: {src})")
            for item in a["patterns"].get("review_structure_patterns", []):
                rev_bullets.append(f"[{item['confidence']}] {item['pattern']} (source: {src})")
            for item in a["patterns"].get("scientific_phrases", []):
                phrase = re.sub(r"\[[^\]]+\]", "[entity]", item["phrase"])
                sci_bullets.append(f"[{item['category']}] {phrase} (source: {src})")

        append_unique_bullets(base_dir / "runtime" / "skills" / "abstract_patterns.md", "Abstract Patterns", abs_bullets)
        append_unique_bullets(base_dir / "runtime" / "skills" / "results_logic_patterns.md", "Results Logic Patterns", res_bullets)
        append_unique_bullets(base_dir / "runtime" / "skills" / "discussion_patterns.md", "Discussion Patterns", dis_bullets)
        append_unique_bullets(base_dir / "runtime" / "skills" / "review_structures.md", "Review Structures", rev_bullets)
        append_unique_bullets(base_dir / "runtime" / "skills" / "scientific_phrases.md", "Scientific Phrases", sci_bullets)

        state = update_learning_state(state, daily_candidates, date_str)
        save_learning_state(learning_state_path, state)

        focus_items = extract_focus_items(state, top_k=6)
        recent_updates = state.get("history", [])[-1].get("updates", []) if state.get("history") else []
        new_items = [u["key"] for u in recent_updates if u.get("count") == 1]
        reinforced = [u["key"] for u in recent_updates if u.get("status") in {"candidate", "high_conf"}]
        uncertain = [f"{a['file_name']}::uncertain_knowledge" for a in valid if any(k.get("uncertain") for k in a.get("knowledge", []))]

        write_evolution_log(
            base_dir / "runtime" / "skills" / "evolution_log.md",
            date_str,
            new_items,
            reinforced,
            uncertain,
            focus_items,
        )

        write_generated_examples(base_dir / "runtime" / "skills" / "generated_examples" / f"{date_str}.md", date_str)

        processed_records.extend(
            {
                "file_path": a["file_path"],
                "file_name": a["file_name"],
                "modified_time": a["modified_time"],
                "file_hash": a["file_hash"],
                "processed_date": a["processed_date"],
                "paper_type": a["paper_type"],
                "quality_flag": a["quality_flag"],
                "status": a["status"],
            }
            for a in analyses
        )
        save_json(processed_path, processed_records)

    logging.info("Done. Analyses: %s", len(analyses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
