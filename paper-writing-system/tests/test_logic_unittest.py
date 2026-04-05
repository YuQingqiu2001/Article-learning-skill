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
from install_openclaw import resolve_codex_home, install_skill, SKILL_NAME
from parser_article import parse_article_structure, label_abstract_sentences
from pdf_reader import _sectionize_lines, _match_section_heading
from parser_review import parse_review_structure, detect_organization_types
from pdf_classifier import classify_paper
from knowledge_extractor import extract_knowledge
from pattern_extractor import abstract_patterns, scientific_phrases


class TestClassifier(unittest.TestCase):
    def test_review_detect_by_filename_single_signal(self) -> None:
        res = classify_paper(
            file_name="oncology_review_2026.pdf",
            text="This paper summarizes evidence.",
            section_headers=["Introduction", "Conclusion"],
        )
        self.assertEqual(res.paper_type, "review")

    def test_review_detect_strong_keyword(self) -> None:
        res = classify_paper(
            file_name="systematic_review_of_cancer.pdf",
            text="A systematic review of treatments.",
            section_headers=["Introduction", "Search Strategy", "Conclusion"],
        )
        self.assertEqual(res.paper_type, "review")
        self.assertGreater(res.score, 0.7)

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


class TestPDFSectionDetection(unittest.TestCase):
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

    def test_match_materials_and_methods(self) -> None:
        self.assertEqual(_match_section_heading("Materials and Methods"), "methods")
        self.assertEqual(_match_section_heading("materials & methods"), "methods")

    def test_match_numbered_sections(self) -> None:
        self.assertEqual(_match_section_heading("1. Introduction"), "introduction")
        self.assertEqual(_match_section_heading("3. Results"), "results")

    def test_no_false_positive_on_long_lines(self) -> None:
        self.assertIsNone(_match_section_heading("This abstract describes something about the introduction of a novel mechanism"))

    def test_section_aliases(self) -> None:
        self.assertEqual(_match_section_heading("Methodology"), "methods")
        self.assertEqual(_match_section_heading("Findings"), "results")
        self.assertEqual(_match_section_heading("Concluding Remarks"), "conclusion")
        self.assertEqual(_match_section_heading("Background"), "introduction")


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

    def test_abstract_semantic_labeling(self) -> None:
        abstract = (
            "Cancer remains a leading cause of death worldwide. "
            "This study aimed to evaluate a novel biomarker. "
            "We recruited 200 patients and measured serum levels. "
            "Results showed a significant increase in the treatment group. "
            "In conclusion, the biomarker has diagnostic potential."
        )
        roles = label_abstract_sentences(abstract)
        self.assertEqual(len(roles), 5)
        # Verify semantic cues work: "remains" -> Background, "aimed" -> Objective, etc.
        self.assertEqual(roles[0]["label"], "Background")
        self.assertEqual(roles[1]["label"], "Objective")
        self.assertEqual(roles[2]["label"], "Methods")
        self.assertEqual(roles[3]["label"], "Results")
        self.assertEqual(roles[4]["label"], "Conclusion")

    def test_discussion_modes_extract_evidence(self) -> None:
        parsed = parse_article_structure(
            text="",
            section_map={
                "abstract": "",
                "introduction": "",
                "methods": "",
                "results": "",
                "discussion": "Our findings suggest that the pathway is critical. This is consistent with prior studies. A limitation of this study is the small sample size.",
            },
        )
        modes = parsed["discussion_modes"]
        self.assertTrue(len(modes["causal_explanation"]) > 0)
        self.assertTrue(len(modes["comparative"]) > 0)
        self.assertTrue(len(modes["limitations"]) > 0)

    def test_review_parser_outputs_organization(self) -> None:
        parsed = parse_review_structure(
            text="Mechanism and pathway based synthesis.",
            section_map={"introduction": "intro", "conclusion": "future directions"},
            headers=["Mechanism section"],
        )
        self.assertIn("mechanism-based", parsed["organization_types_detected"])

    def test_review_parser_multiple_org_types(self) -> None:
        parsed = parse_review_structure(
            text="The mechanism of the disease involves signaling pathways.",
            section_map={"introduction": "intro", "conclusion": "concl"},
            headers=["Disease mechanisms"],
        )
        org_types = parsed["organization_types_detected"]
        self.assertGreaterEqual(len(org_types), 1)


class TestAIReviewGuard(unittest.TestCase):
    def test_ai_review_flags_low_quality_uncertain(self) -> None:
        report = simulate_ai_review(
            {
                "paper_type": "uncertain",
                "quality_flag": "low",
                "detected_sections": [],
                "patterns": {},
                "knowledge": [],
            }
        )
        self.assertTrue(report["needs_human_guidance"])
        self.assertGreater(len(report["questions"]), 0)

    def test_ai_review_passes_good_paper(self) -> None:
        """A well-extracted article should NOT be flagged."""
        report = simulate_ai_review(
            {
                "paper_type": "article",
                "quality_flag": "high",
                "detected_sections": ["abstract", "introduction", "methods", "results", "discussion"],
                "patterns": {"abstract_patterns": [{"pattern": "test"}]},
                "knowledge": [{"uncertain": False}],
            }
        )
        self.assertFalse(report["needs_human_guidance"])
        self.assertGreaterEqual(report["agreement_score"], 0.9)

    def test_ai_review_medium_quality_not_flagged(self) -> None:
        """Medium quality articles should not be automatically flagged."""
        report = simulate_ai_review(
            {
                "paper_type": "article",
                "quality_flag": "medium",
                "detected_sections": ["abstract", "methods", "results"],
                "patterns": {"abstract_patterns": [{"pattern": "test"}]},
                "knowledge": [{"uncertain": False}],
            }
        )
        self.assertFalse(report["needs_human_guidance"])

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


class TestKnowledgeExtractor(unittest.TestCase):
    def test_review_default_trend(self) -> None:
        """Review with no keyword hits should still produce a trend item."""
        items = extract_knowledge("This is a general overview.", "review")
        self.assertTrue(len(items) >= 1)
        self.assertEqual(items[-1]["type"], "研究趋势")
        self.assertFalse(items[-1]["uncertain"])

    def test_article_confidence_levels(self) -> None:
        """Articles with single hit should have low confidence, multi-hit medium."""
        items = extract_knowledge("The pathway involves gene expression.", "article")
        self.assertTrue(len(items) >= 1)
        # "pathway" matches mechanism, "gene" matches gene/molecular
        mechanism_item = next((i for i in items if i["type"] == "新机制或通路"), None)
        self.assertIsNotNone(mechanism_item)

    def test_multi_hit_boosts_confidence(self) -> None:
        items = extract_knowledge("The signaling pathway and mechanism are clear.", "article")
        mechanism_item = next((i for i in items if i["type"] == "新机制或通路"), None)
        self.assertIsNotNone(mechanism_item)
        self.assertEqual(mechanism_item["confidence"], "medium")  # multi-hit boost


class TestPatternExtractor(unittest.TestCase):
    def test_abstract_patterns_from_roles(self) -> None:
        analysis = {
            "paper_type": "article",
            "parsed": {
                "abstract_roles": [
                    {"label": "Background", "sentence": "x"},
                    {"label": "Objective", "sentence": "y"},
                    {"label": "Methods", "sentence": "z"},
                    {"label": "Results", "sentence": "w"},
                    {"label": "Conclusion", "sentence": "v"},
                ],
            },
        }
        patterns = abstract_patterns(analysis)
        self.assertEqual(len(patterns), 1)
        self.assertIn("Background", patterns[0]["pattern"])
        self.assertEqual(patterns[0]["confidence"], "high")

    def test_scientific_phrases_extract_from_content(self) -> None:
        analysis = {
            "paper_type": "article",
            "parsed": {
                "sections": {
                    "results": "The treatment was associated with a significant reduction in tumor size (p < 0.001).",
                    "discussion": "These findings suggest that the drug inhibits cell growth. This is consistent with previous reports.",
                    "conclusion": "Our study provides new insights into targeted therapy.",
                },
            },
        }
        phrases = scientific_phrases(analysis)
        # Should extract real phrases from content
        self.assertTrue(len(phrases) >= 1)
        # Check that at least one phrase was generalized from actual text
        categories = {p["category"] for p in phrases}
        self.assertTrue(len(categories) >= 1)


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

    def test_allow_deposit_works_for_failed_extract(self) -> None:
        """allow_deposit should work for any non-ok status, not just needs_human_guidance."""
        analysis = {
            "file_name": "b.pdf",
            "paper_type": "article",
            "status": "failed_extract",
        }
        feedback = {"allow_deposit": True}
        updated = apply_feedback(analysis, feedback)
        self.assertEqual(updated["status"], "ok")


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

    def test_balanced_thresholds(self) -> None:
        """Both review and article papers should be able to reach high_conf."""
        state = {"version": "0.2", "patterns": {}, "history": []}

        # 3 article papers with high quality
        candidates = [
            PatternCandidate("results_logic", "pattern_a", f"art{i}.pdf", "high", "article", "high")
            for i in range(3)
        ]
        state = update_learning_state(state, candidates, "2026-04-05")
        key = "results_logic::pattern_a"
        self.assertEqual(state["patterns"][key]["status"], "high_conf")

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
