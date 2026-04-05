"""Manual entrypoint for paper-writing-system v0.1 skeleton."""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path
from typing import Any

from ai_review_guard import simulate_ai_review
from feedback_loop import apply_feedback, load_feedback_map
from knowledge_extractor import extract_knowledge
from learning_engine import PatternCandidate, extract_focus_items, load_learning_state, save_learning_state, update_learning_state
from output_writer import append_unique_bullets, write_daily_memory, write_evolution_log, write_generated_examples, write_human_questions
from parser_article import parse_article_structure
from pdf_reader import extract_pdf_content
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
    parser.add_argument("--max-files", type=int, default=0, help="Max number of PDFs to process (0 means no limit)")
    parser.add_argument("--stop-on-bias", action="store_true", help="Stop run when one paper is flagged by AI review")
    parser.add_argument("--feedback-file", default="", help="Optional JSON file for human feedback overrides")
    parser.add_argument("--max-pages", type=int, default=30, help="Max PDF pages to read per paper")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(levelname)s: %(message)s")


def extract_text_and_sections(pdf_path: Path, max_pages: int) -> tuple[str, list[str], dict[str, str], dict[str, Any]]:
    """Extract plain text and rough section map from PDF.

    Uses robust multi-column capable backend when available.
    """
    return extract_pdf_content(pdf_path, max_pages=max_pages)


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




def learning_priority_key(analysis: dict[str, Any]) -> tuple[int, int]:
    """Higher priority first: review > article, high quality > medium."""
    type_score = 2 if analysis.get("paper_type") == "review" else 1
    q = analysis.get("quality_flag")
    quality_score = 3 if q == "high" else 2 if q == "medium" else 1
    return type_score, quality_score


def main() -> int:
    args = parse_args()
    configure_logging(args.verbose)

    base_dir = Path(__file__).resolve().parents[1]
    ensure_runtime_structure(base_dir)

    processed_path = base_dir / "runtime" / "processed_files.json"
    processed_records: list[dict[str, Any]] = load_json(processed_path, default=[])
    processed_index = {(r.get("file_path"), r.get("file_hash")) for r in processed_records}

    input_path = Path(args.input_dir)
    pdfs = scan_recent_pdfs(input_path, args.days)
    if args.max_files and args.max_files > 0:
        pdfs = pdfs[: args.max_files]
    logging.info("Found %s recent PDF(s).", len(pdfs))

    analyses: list[dict[str, Any]] = []
    date_str = today_str()
    human_guidance_entries: list[dict[str, Any]] = []
    feedback_map = load_feedback_map(Path(args.feedback_file)) if args.feedback_file else {}

    seen_this_run: set[tuple[str, str]] = set()
    for pdf in pdfs:
        key = (normalize_windows_path(pdf.path), pdf.file_hash)
        if key in seen_this_run:
            logging.debug("Skip duplicated file in current run: %s", pdf.path)
            continue
        seen_this_run.add(key)
        if not args.force and key in processed_index:
            logging.debug("Skip already processed: %s", pdf.path)
            continue

        try:
            text, headers, sections, reader_meta = extract_text_and_sections(pdf.path, max_pages=args.max_pages)
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
                "reader_backend": reader_meta.get("backend", "unknown"),
            }
            analysis["pattern_brief"] = [p.get("pattern", p.get("phrase", "")) for group in analysis["patterns"].values() for p in group][:4]

            # One-by-one learning guard: immediately verify each paper via AI review.
            review_report = simulate_ai_review(analysis)
            analysis["ai_review"] = review_report
            if review_report.get("needs_human_guidance"):
                analysis["status"] = "needs_human_guidance"
                human_guidance_entries.append(
                    {
                        "file_name": analysis["file_name"],
                        "agreement_score": review_report.get("agreement_score"),
                        "issues": review_report.get("issues", []),
                        "questions": review_report.get("questions", []),
                    }
                )

            # Human feedback loop: allow curated override from previous guidance cycle.
            if analysis["file_name"] in feedback_map:
                analysis = apply_feedback(analysis, feedback_map[analysis["file_name"]])

            if args.stop_on_bias and analysis.get("status") == "needs_human_guidance":
                analyses.append(analysis)
                logging.warning("Stopped by --stop-on-bias due to %s", analysis["file_name"])
                break

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
        msg = "无新增文献" if input_path.exists() else f"输入目录不存在: {args.input_dir}"
        write_daily_memory(memory_file, date_str, analyses, message=msg)
        write_human_questions(base_dir / "runtime" / "memory" / f"human_questions_{date_str}.md", date_str, human_guidance_entries)
        logging.info("No new files to process.")
        return 0

    write_daily_memory(memory_file, date_str, analyses)
    write_human_questions(base_dir / "runtime" / "memory" / f"human_questions_{date_str}.md", date_str, human_guidance_entries)

    if not args.dry_run:
        # 仅沉淀高质量且非失败结果
        valid = [a for a in analyses if a["status"] == "ok" and a["quality_flag"] != "low"]
        valid.sort(key=learning_priority_key, reverse=True)

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
        # de-duplicate by (file_path, file_hash), keeping latest record
        unique_map: dict[tuple[str, str], dict[str, Any]] = {}
        for rec in processed_records:
            key = (rec.get("file_path", ""), rec.get("file_hash", ""))
            unique_map[key] = rec
        save_json(processed_path, list(unique_map.values()))

    logging.info("Done. Analyses: %s", len(analyses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
