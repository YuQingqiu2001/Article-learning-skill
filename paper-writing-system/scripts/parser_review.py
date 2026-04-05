"""Parser for Review papers."""
from __future__ import annotations

from typing import Any


REVIEW_KEYS = ["abstract", "introduction", "conclusion"]


def parse_review_structure(text: str, section_map: dict[str, str], headers: list[str]) -> dict[str, Any]:
    """Extract review-specific structure.

    TODO: Replace with hierarchical heading parser and paragraph-level logic parser.
    """
    org_type = detect_organization_type(text, headers)
    claim_evidence_synthesis = build_ces_placeholders(section_map)

    return {
        "sections": {k: section_map.get(k, "")[:2000] for k in REVIEW_KEYS},
        "main_sections": headers[:12],
        "organization_type": org_type,
        "claim_evidence_synthesis": claim_evidence_synthesis,
        "high_level_writing": {
            "knowledge_gap": "Placeholder from conclusion/introduction signals",
            "future_directions": "Placeholder from future/research-needed signals",
            "clinical_implications": "Placeholder from translational/clinical signals",
        },
    }


def detect_organization_type(text: str, headers: list[str]) -> str:
    low = (text + " " + " ".join(headers)).lower()
    if "mechanism" in low or "pathway" in low:
        return "mechanism-based"
    if "disease" in low or "syndrome" in low:
        return "disease-based"
    if "method" in low or "technique" in low:
        return "method-based"
    if "history" in low or "timeline" in low:
        return "timeline-based"
    return "mixed"


def build_ces_placeholders(section_map: dict[str, str]) -> list[dict[str, str]]:
    intro = section_map.get("introduction", "")[:300]
    concl = section_map.get("conclusion", "")[:300]
    return [
        {
            "claim": "Core thematic claim placeholder",
            "evidence": intro,
            "synthesis": concl,
        }
    ]
