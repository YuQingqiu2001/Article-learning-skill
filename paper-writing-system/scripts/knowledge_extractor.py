"""Conservative knowledge extractor with uncertainty tagging."""
from __future__ import annotations

import re
from typing import Any

# Use word-boundary matching to avoid substring false positives
# (e.g. "gene" matching "general", "method" matching "methodology").
_MECHANISM_RE = re.compile(r"\b(?:pathway|mechanism|signaling)\b", re.IGNORECASE)
_MOLECULAR_RE = re.compile(r"\b(?:genes?|protein|molecular|receptor|enzyme)\b", re.IGNORECASE)
_STUDY_RE = re.compile(r"\b(?:randomized|cohort|meta-analysis|cross-sectional|case-control)\b", re.IGNORECASE)


def extract_knowledge(text: str, paper_type: str) -> list[dict[str, Any]]:
    """Extract lightweight knowledge items.

    TODO: Replace keyword-based extraction with evidence-grounded semantic extractor.
    """
    items: list[dict[str, Any]] = []

    if _MECHANISM_RE.search(text):
        items.append(_item("新机制或通路", "Potential mechanism/pathway discussed", paper_type))
    if _MOLECULAR_RE.search(text):
        items.append(_item("基因或分子", "Potential gene/molecular factor reported", paper_type))
    if _STUDY_RE.search(text):
        items.append(_item("研究方法", "Potential study design pattern detected", paper_type))
    if paper_type == "review":
        items.append(
            {
                "type": "研究趋势",
                "summary": "Review-level trend synthesis candidate",
                "stability": "cautious",
                "confidence": "medium",
                "uncertain": True,
            }
        )
    return items


def _item(kind: str, summary: str, paper_type: str) -> dict[str, Any]:
    confidence = "medium" if paper_type == "review" else "low"
    return {
        "type": kind,
        "summary": summary,
        "stability": "contested" if confidence == "low" else "cautious",
        "confidence": confidence,
        "uncertain": confidence != "high",
    }
