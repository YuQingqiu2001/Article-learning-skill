"""Conservative knowledge extractor with uncertainty tagging."""
from __future__ import annotations

from typing import Any


def extract_knowledge(text: str, paper_type: str) -> list[dict[str, Any]]:
    """Extract lightweight knowledge items.

    TODO: Replace keyword-based extraction with evidence-grounded semantic extractor.
    """
    low = text.lower()
    items: list[dict[str, Any]] = []

    if "pathway" in low or "mechanism" in low:
        items.append(_item("新机制或通路", "Potential mechanism/pathway discussed", paper_type))
    if "gene" in low or "protein" in low or "molecular" in low:
        items.append(_item("基因或分子", "Potential gene/molecular factor reported", paper_type))
    if "randomized" in low or "cohort" in low or "meta-analysis" in low:
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
