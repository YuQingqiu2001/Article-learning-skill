"""Parser for Original Article style papers."""
from __future__ import annotations

import re
from typing import Any


SECTION_KEYS = ["abstract", "introduction", "methods", "results", "discussion"]


def parse_article_structure(text: str, section_map: dict[str, str]) -> dict[str, Any]:
    """Extract article-specific structure and placeholders.

    TODO: Upgrade to paragraph-level parsing with robust section boundary detection.
    """
    abstract = section_map.get("abstract", "")
    abstract_roles = label_abstract_sentences(abstract)
    findings = split_findings(section_map.get("results", ""))
    discussion_modes = extract_discussion_modes(section_map.get("discussion", ""))

    return {
        "sections": {k: section_map.get(k, "")[:2000] for k in SECTION_KEYS},
        "abstract_roles": abstract_roles,
        "results_finding_units": findings,
        "results_progression": [f"Result{i + 1}" for i in range(len(findings))],
        "discussion_modes": discussion_modes,
    }


def label_abstract_sentences(abstract: str) -> list[dict[str, str]]:
    labels = ["Background", "Objective", "Methods", "Results", "Conclusion"]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    tagged = []
    for idx, sent in enumerate(sentences):
        label = labels[min(idx, len(labels) - 1)]
        tagged.append({"label": label, "sentence": sent})
    return tagged


def split_findings(results_text: str) -> list[dict[str, str]]:
    parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=\.)\s+(?=We|Our|These|This)", results_text) if p.strip()]
    units: list[dict[str, str]] = []
    for p in parts[:5]:
        units.append(
            {
                "question": "What does this result attempt to test?",
                "method": "Method placeholder (rule-based extraction)",
                "result": p[:300],
                "reasoning": "Reasoning placeholder",
                "transition": "Transition to next finding",
            }
        )
    return units


def extract_discussion_modes(discussion_text: str) -> dict[str, list[str]]:
    lower = discussion_text.lower()
    return {
        "causal_explanation": ["Detected" if "because" in lower or "suggest" in lower else "Not clear"],
        "comparative": ["Detected" if "consistent with" in lower or "compared with" in lower else "Not clear"],
        "limitations": ["Detected" if "limitation" in lower else "Not clear"],
        "biological_significance": ["Detected" if "mechanism" in lower or "pathway" in lower else "Not clear"],
        "clinical_significance": ["Detected" if "clinical" in lower else "Not clear"],
    }
