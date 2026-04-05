"""Rule-based paper type classifier."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ClassificationResult:
    paper_type: str  # article/review/uncertain
    score: float
    evidence: list[str]


def classify_paper(file_name: str, text: str, section_headers: list[str]) -> ClassificationResult:
    """Classify as article/review/uncertain using lightweight heuristics.

    TODO: Replace with a robust classifier (LLM or fine-tuned model) in future versions.
    """
    name = file_name.lower()
    t = text.lower()
    headers = " ".join(section_headers).lower()

    review_keywords = ["review", "systematic review", "meta-analysis", "narrative review"]
    article_markers = ["methods", "results", "discussion", "materials and methods"]

    evidence: list[str] = []
    review_score = sum(1 for k in review_keywords if k in name or k in t)
    article_score = sum(1 for k in article_markers if k in headers or k in t)

    if review_score >= 2 and review_score >= article_score:
        evidence.append("review_keywords")
        return ClassificationResult("review", min(0.95, 0.6 + review_score * 0.1), evidence)

    if article_score >= 2:
        evidence.append("imrad_markers")
        return ClassificationResult("article", min(0.95, 0.6 + article_score * 0.08), evidence)

    evidence.append("weak_signals")
    return ClassificationResult("uncertain", 0.4, evidence)
