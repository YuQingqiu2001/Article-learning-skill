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


_ROLE_CUES: list[tuple[str, list[str]]] = [
    ("Background", ["background", "currently", "recent studies", "it is known", "emerging", "prevalence", "has been", "remains"]),
    ("Objective", ["aim", "objective", "purpose", "this study", "we examined", "aimed", "sought to", "investigated", "determine whether"]),
    ("Methods", ["method", "participant", "sample", "recruited", "performed", "analyzed", "measured", "collected", "randomized", "enrolled"]),
    ("Results", ["result", "found", "showed", "demonstrated", "observed", "significant", "increased", "decreased", "associated", "p <", "p="]),
    ("Conclusion", ["conclusion", "conclude", "suggest", "implication", "in summary", "taken together", "these findings", "overall"]),
]


def label_abstract_sentences(abstract: str) -> list[dict[str, str]]:
    """Label abstract sentences using semantic cues, with positional fallback."""
    labels = ["Background", "Objective", "Methods", "Results", "Conclusion"]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    if not sentences:
        return []

    tagged = []
    for idx, sent in enumerate(sentences):
        sent_lower = sent.lower()
        best_label = None
        best_score = 0

        for role, cues in _ROLE_CUES:
            score = sum(1 for cue in cues if cue in sent_lower)
            if score > best_score:
                best_score = score
                best_label = role

        if best_label is None or best_score == 0:
            # Fallback: assign by relative position in abstract
            pos = idx / max(len(sentences), 1)
            label_idx = min(int(pos * len(labels)), len(labels) - 1)
            best_label = labels[label_idx]

        tagged.append({"label": best_label, "sentence": sent})
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
