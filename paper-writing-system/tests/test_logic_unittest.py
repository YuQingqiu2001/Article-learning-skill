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

from learning_engine import PatternCandidate, extract_focus_items, load_learning_state, update_learning_state
from output_writer import append_unique_bullets
from parser_article import parse_article_structure
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
