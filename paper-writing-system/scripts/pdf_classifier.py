"""Rule-based paper type classifier with improved heuristics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ClassificationResult:
    paper_type: str  # article/review/uncertain
    score: float
    evidence: list[str] = field(default_factory=list)


# Strong review signals (typically in title or abstract).
_REVIEW_STRONG = ["systematic review", "meta-analysis", "narrative review", "scoping review", "literature review"]
# Weaker review signals (common but can appear in any paper).
_REVIEW_WEAK = ["review"]
# IMRaD section markers (typically in section headings).
_ARTICLE_MARKERS = ["methods", "results", "discussion", "materials and methods"]


def classify_paper(file_name: str, text: str, section_headers: list[str]) -> ClassificationResult:
    """Classify as article/review/uncertain using improved heuristics.

    Uses a weighted scoring approach:
    - Strong review keywords (systematic review, meta-analysis) get higher weight.
    - IMRaD section headers get higher weight than body text matches.
    - Considers both title/filename and body signals.
    """
    name_lower = file_name.lower()
    text_lower = text[:5000].lower()  # Focus on title/abstract area
    headers_lower = " ".join(section_headers).lower()

    evidence: list[str] = []
    review_score = 0.0
    article_score = 0.0

    # --- Review signals ---
    for kw in _REVIEW_STRONG:
        if kw in name_lower:
            review_score += 2.0
            evidence.append(f"strong_review_in_filename:{kw}")
        if kw in text_lower:
            review_score += 1.5
            evidence.append(f"strong_review_in_text:{kw}")

    for kw in _REVIEW_WEAK:
        if kw in name_lower and not any(s in name_lower for s in _REVIEW_STRONG):
            review_score += 0.8
            evidence.append(f"weak_review_in_filename:{kw}")

    # --- Article signals ---
    for kw in _ARTICLE_MARKERS:
        if kw in headers_lower:
            article_score += 1.5  # Headers are strong evidence of IMRaD structure
            evidence.append(f"imrad_header:{kw}")
        elif kw in text_lower:
            article_score += 0.5
            evidence.append(f"imrad_in_text:{kw}")

    # Check for typical article structures: numbered figures/tables suggest original research
    if re.search(r"(?:figure|fig\.?|table)\s+\d", text_lower):
        article_score += 0.5
        evidence.append("has_figures_or_tables")

    # --- Decision ---
    if review_score >= 2.0 and review_score > article_score:
        confidence = min(0.95, 0.6 + review_score * 0.08)
        return ClassificationResult("review", round(confidence, 3), evidence)

    if review_score >= 0.8 and article_score <= 1.0:
        return ClassificationResult("review", 0.65, evidence)

    if article_score >= 3.0:
        confidence = min(0.95, 0.6 + article_score * 0.06)
        return ClassificationResult("article", round(confidence, 3), evidence)

    if article_score >= 1.5:
        return ClassificationResult("article", 0.6, evidence)

    evidence.append("weak_signals")
    return ClassificationResult("uncertain", 0.4, evidence)
