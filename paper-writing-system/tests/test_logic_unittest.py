"""Regression checks for paper-writing-system logic.

Run:
  python -m unittest discover -s tests -p 'test_*.py' -v
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

# Allow importing from ../scripts
import sys

THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = THIS_DIR.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ai_review_guard import simulate_ai_review
from feedback_loop import apply_feedback, load_feedback_map
from learning_engine import PatternCandidate, extract_focus_items, load_learning_state, update_learning_state
from output_writer import append_unique_bullets, write_human_questions
from openclaw_entry import build_args_from_env
from install_openclaw import resolve_codex_home, install_skill, validate_install, SKILL_NAME
from parser_article import parse_article_structure
from pdf_reader import _sectionize_lines
from parser_review import parse_review_structure
from pdf_classifier import classify_paper


class TestClassifier(unittest.TestCase):
    def test_review_detect_by_filename_single_signal(self) -> None:
        res = classify_paper(
            file_name="oncology_review_2026.pdf",
            text="This paper summarizes evidence.",
            section_headers=["Introduction", "Conclusion"],
        )
        self.assertEqual(res.paper_type, "review")

    def test_article_detect_by_imrad(self) -> None:
        res = classify_paper(
            file_name="original_study.pdf",
            text="Methods and Results show ... Discussion ...",
            section_headers=["Methods", "Results", "Discussion"],
        )
        self.assertEqual(res.paper_type, "article")


    def test_uncertain_when_signals_weak(self) -> None:
        res = classify_paper(
            file_name="paper_misc.pdf",
            text="General discussion without clear structure.",
            section_headers=["Background"],
        )
        self.assertEqual(res.paper_type, "uncertain")


class TestParsers(unittest.TestCase):
    def test_article_parser_outputs_required_blocks(self) -> None:
        parsed = parse_article_structure(
            text="",
            section_map={
                "abstract": "A. B. C. D. E.",
                "introduction": "intro",
                "methods": "methods",
                "results": "We observed a significant increase (p < 0.05). Furthermore, this suggests improved response.",
                "discussion": "This result suggests a mechanism and is consistent with previous study.",
            },
        )
        self.assertIn("abstract_roles", parsed)
        self.assertIn("results_finding_units", parsed)
        self.assertIn("discussion_modes", parsed)
        self.assertIn("Evidence:", parsed["results_finding_units"][0]["reasoning"])
        self.assertIn("reasoning_chain", parsed["discussion_modes"])

    def test_review_parser_outputs_organization(self) -> None:
        parsed = parse_review_structure(
            text="Mechanism and pathway based synthesis.",
            section_map={
                "introduction": "This review suggests a pathway-level model. Evidence from recent studies demonstrated repeatability.",
                "conclusion": "In summary, these data support an integrated framework for future work.",
            },
            headers=["Mechanism section"],
        )
        self.assertIn(parsed["organization_type"], {"mechanism-based", "disease-based", "method-based", "timeline-based", "mixed"})
        self.assertTrue(parsed["claim_evidence_synthesis"][0]["claim"])
        self.assertTrue(parsed["claim_evidence_synthesis"][0]["evidence"])


class TestPDFReader(unittest.TestCase):
    def test_sectionize_lines_handles_imrad_headers(self) -> None:
        text, headers, section_map = _sectionize_lines(
            [
                "Abstract",
                "A summary.",
                "Introduction",
                "Intro body.",
                "Methods",
                "Method body.",
                "Results",
                "Result body.",
                "Discussion",
                "Discussion body.",
            ]
        )
        self.assertTrue(text)
        self.assertIn("Abstract", headers)
        self.assertIn("abstract", section_map)
        self.assertIn("results", section_map)


class TestAIReviewGuard(unittest.TestCase):
    def test_ai_review_flags_low_quality_uncertain(self) -> None:
        report = simulate_ai_review(
            {
                "paper_type": "uncertain",
                "quality_flag": "low",
                "detected_sections": [],
                "patterns": {},
            }
        )
        self.assertTrue(report["needs_human_guidance"])
        self.assertGreaterEqual(len(report["questions"]), 3)


    def test_ai_review_passes_high_quality_case(self) -> None:
        report = simulate_ai_review(
            {
                "paper_type": "review",
                "quality_flag": "high",
                "detected_sections": ["abstract", "introduction", "conclusion"],
                "patterns": {"abstract_patterns": [{"pattern": "x"}]},
            }
        )
        self.assertFalse(report["needs_human_guidance"])
        self.assertGreaterEqual(report["agreement_score"], 0.8)

    def test_write_human_questions_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "human_questions_2026-04-05.md"
            write_human_questions(
                target,
                "2026-04-05",
                [
                    {
                        "file_name": "a.pdf",
                        "agreement_score": 0.4,
                        "issues": ["low quality"],
                        "questions": ["Q1", "Q2", "Q3"],
                    }
                ],
            )
            text = target.read_text(encoding="utf-8")
            self.assertIn("a.pdf", text)
            self.assertIn("Q1", text)


class TestOpenclawEntry(unittest.TestCase):
    def test_build_args_from_env_prefers_clawhub(self) -> None:
        import os

        backup = dict(os.environ)
        try:
            os.environ["OPENCLAW_INPUT_DIR"] = r"D:\legacy"
            os.environ["CLAWHUB_INPUT_DIR"] = r"D:\sci文献数据"
            os.environ["CLAWHUB_DAYS"] = "2"
            os.environ["CLAWHUB_DRY_RUN"] = "1"
            os.environ["CLAWHUB_FORCE"] = "1"
            os.environ["CLAWHUB_VERBOSE"] = "1"
            os.environ["CLAWHUB_MAX_FILES"] = "3"
            os.environ["CLAWHUB_STOP_ON_BIAS"] = "1"
            os.environ["CLAWHUB_FEEDBACK_FILE"] = "feedback.json"
            os.environ["CLAWHUB_MAX_PAGES"] = "25"
            os.environ["CLAWHUB_MANUAL_TRIGGER"] = "1"

            args = build_args_from_env()
            self.assertIn("--input-dir", args)
            self.assertIn(r"D:\sci文献数据", args)
            self.assertIn("--days", args)
            self.assertIn("--max-files", args)
            self.assertIn("--max-pages", args)
            self.assertIn("--dry-run", args)
            self.assertIn("--force", args)
            self.assertIn("--verbose", args)
            self.assertIn("--stop-on-bias", args)
            self.assertIn("--feedback-file", args)
            self.assertIn("--manual-trigger", args)
        finally:
            os.environ.clear()
            os.environ.update(backup)

    def test_build_args_from_env_manual_trigger_off(self) -> None:
        import os

        backup = dict(os.environ)
        try:
            os.environ["CLAWHUB_MANUAL_TRIGGER"] = "0"
            args = build_args_from_env()
            self.assertNotIn("--manual-trigger", args)
        finally:
            os.environ.clear()
            os.environ.update(backup)


class TestFeedbackLoop(unittest.TestCase):
    def test_load_feedback_map_and_apply(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "feedback.json"
            fp.write_text(
                json.dumps(
                    {
                        "a.pdf": {
                            "paper_type": "review",
                            "learn_focus": "mechanism",
                            "allow_deposit": True,
                            "notes": "confirmed by human",
                        }
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            m = load_feedback_map(fp)
            self.assertIn("a.pdf", m)

            analysis = {
                "file_name": "a.pdf",
                "paper_type": "uncertain",
                "status": "needs_human_guidance",
            }
            updated = apply_feedback(analysis, m["a.pdf"])
            self.assertEqual(updated["paper_type"], "review")
            self.assertEqual(updated["status"], "ok")
            self.assertEqual(updated["learn_focus"], "mechanism")


class TestInstaller(unittest.TestCase):
    def test_resolve_codex_home_default_or_env(self) -> None:
        import os

        backup = os.environ.get("CODEX_HOME")
        backup_clawhub = os.environ.get("CLAWHUB_HOME")
        try:
            os.environ["CLAWHUB_HOME"] = "./tmp_clawhub_home_test"
            os.environ["CODEX_HOME"] = "./tmp_codex_home_test"
            resolved = resolve_codex_home("")
            self.assertTrue(str(resolved).endswith("tmp_clawhub_home_test"))
        finally:
            if backup is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = backup
            if backup_clawhub is None:
                os.environ.pop("CLAWHUB_HOME", None)
            else:
                os.environ["CLAWHUB_HOME"] = backup_clawhub

    def test_install_skill_dry_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = install_skill(Path(td), force=False)
            self.assertTrue(target.exists())
            self.assertEqual(target.name, SKILL_NAME)
            ok, missing = validate_install(target)
            self.assertTrue(ok)
            self.assertEqual(missing, [])


class TestLearningAndDedup(unittest.TestCase):
    def test_learning_state_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "state.json"
            state = load_learning_state(p)
            candidates = [
                PatternCandidate("abstract_patterns", "B-O-M-R-C", "a.pdf", "high", "review", "high"),
                PatternCandidate("abstract_patterns", "B-O-M-R-C", "b.pdf", "high", "review", "high"),
                PatternCandidate("abstract_patterns", "B-O-M-R-C", "c.pdf", "high", "review", "high"),
            ]
            state = update_learning_state(state, candidates, "2026-04-05")
            focus = extract_focus_items(state, top_k=3)
            self.assertTrue(focus)
            self.assertIn(focus[0]["status"], {"candidate", "high_conf"})

    def test_semantic_dedup_for_skill_bullets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "patterns.md"
            append_unique_bullets(
                f,
                "Patterns",
                [
                    "[high] Background -> Objective -> Methods -> Results -> Conclusion (source: p1.pdf)",
                    "[high] Background -> Objective -> Methods -> Results -> Conclusion (source: p2.pdf)",
                ],
            )
            txt = f.read_text(encoding="utf-8")
            self.assertEqual(txt.count("Background -> Objective -> Methods -> Results -> Conclusion"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
