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
from knowledge_extractor import extract_knowledge
from learning_engine import PatternCandidate, extract_focus_items, load_learning_state, update_learning_state
from output_writer import append_unique_bullets, write_human_questions
from openclaw_entry import build_args_from_env
from install_openclaw import resolve_codex_home, install_skill, SKILL_NAME
from parser_article import parse_article_structure, label_abstract_sentences
from pdf_reader import _sectionize_lines, _match_section_heading
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
                "results": "We found one. We found two.",
                "discussion": "This suggests mechanism and clinical impact.",
            },
        )
        self.assertIn("abstract_roles", parsed)
        self.assertIn("results_finding_units", parsed)
        self.assertIn("discussion_modes", parsed)

    def test_review_parser_outputs_organization(self) -> None:
        parsed = parse_review_structure(
            text="Mechanism and pathway based synthesis.",
            section_map={"introduction": "intro", "conclusion": "future directions"},
            headers=["Mechanism section"],
        )
        self.assertIn(parsed["organization_type"], {"mechanism-based", "disease-based", "method-based", "timeline-based", "mixed"})


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
    def test_build_args_from_env(self) -> None:
        import os

        backup = dict(os.environ)
        try:
            os.environ["OPENCLAW_INPUT_DIR"] = r"D:\sci文献数据"
            os.environ["OPENCLAW_DAYS"] = "2"
            os.environ["OPENCLAW_DRY_RUN"] = "1"
            os.environ["OPENCLAW_FORCE"] = "1"
            os.environ["OPENCLAW_VERBOSE"] = "1"
            os.environ["OPENCLAW_MAX_FILES"] = "3"
            os.environ["OPENCLAW_STOP_ON_BIAS"] = "1"
            os.environ["OPENCLAW_FEEDBACK_FILE"] = "feedback.json"
            os.environ["OPENCLAW_MAX_PAGES"] = "25"

            args = build_args_from_env()
            self.assertIn("--input-dir", args)
            self.assertIn("--days", args)
            self.assertIn("--max-files", args)
            self.assertIn("--max-pages", args)
            self.assertIn("--dry-run", args)
            self.assertIn("--force", args)
            self.assertIn("--verbose", args)
            self.assertIn("--stop-on-bias", args)
            self.assertIn("--feedback-file", args)
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
        try:
            os.environ["CODEX_HOME"] = "./tmp_codex_home_test"
            resolved = resolve_codex_home("")
            self.assertTrue(str(resolved).endswith("tmp_codex_home_test"))
        finally:
            if backup is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = backup

    def test_install_skill_dry_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = install_skill(Path(td), force=False)
            self.assertTrue(target.exists())
            self.assertEqual(target.name, SKILL_NAME)


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


class TestKnowledgeExtractor(unittest.TestCase):
    def test_no_false_positive_gene_in_general(self) -> None:
        """'gene' keyword must not match 'general'."""
        items = extract_knowledge("This is a general overview of the topic.", "article")
        types = [i["type"] for i in items]
        self.assertNotIn("基因或分子", types)

    def test_gene_matches_actual_gene(self) -> None:
        items = extract_knowledge("The gene expression was significantly upregulated.", "article")
        types = [i["type"] for i in items]
        self.assertIn("基因或分子", types)


class TestAbstractLabeling(unittest.TestCase):
    def test_semantic_labels_over_positional(self) -> None:
        abstract = (
            "Cancer remains a leading cause of death. "
            "This study aimed to evaluate a novel biomarker. "
            "We recruited 200 patients and measured serum levels. "
            "Results showed a significant increase. "
            "In conclusion, this has diagnostic potential."
        )
        roles = label_abstract_sentences(abstract)
        self.assertEqual(len(roles), 5)
        self.assertEqual(roles[0]["label"], "Background")
        self.assertEqual(roles[1]["label"], "Objective")
        self.assertEqual(roles[2]["label"], "Methods")
        self.assertEqual(roles[3]["label"], "Results")
        self.assertEqual(roles[4]["label"], "Conclusion")

    def test_three_sentence_abstract_not_all_same(self) -> None:
        """A 3-sentence abstract should not have all sentences labeled 'Conclusion'."""
        roles = label_abstract_sentences("Background info. We aimed to test X. In conclusion, Y.")
        labels = [r["label"] for r in roles]
        self.assertNotEqual(labels, ["Conclusion", "Conclusion", "Conclusion"])


class TestSectionHeadingDetection(unittest.TestCase):
    def test_materials_and_methods(self) -> None:
        self.assertEqual(_match_section_heading("Materials and Methods"), "methods")
        self.assertEqual(_match_section_heading("Materials & Methods"), "methods")

    def test_numbered_sections(self) -> None:
        self.assertEqual(_match_section_heading("1. Introduction"), "introduction")
        self.assertEqual(_match_section_heading("3. Results"), "results")

    def test_aliases(self) -> None:
        self.assertEqual(_match_section_heading("Methodology"), "methods")
        self.assertEqual(_match_section_heading("Findings"), "results")
        self.assertEqual(_match_section_heading("Background"), "introduction")
        self.assertEqual(_match_section_heading("Conclusions"), "conclusion")

    def test_long_line_rejected(self) -> None:
        self.assertIsNone(_match_section_heading("Abstract of a study about the introduction of new methods in this field"))


class TestFeedbackAllowDeposit(unittest.TestCase):
    def test_allow_deposit_for_failed_extract(self) -> None:
        analysis = {"file_name": "b.pdf", "paper_type": "article", "status": "failed_extract"}
        updated = apply_feedback(analysis, {"allow_deposit": True})
        self.assertEqual(updated["status"], "ok")


if __name__ == "__main__":
    unittest.main(verbosity=2)
