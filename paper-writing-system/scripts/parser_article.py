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
        evidence = _extract_evidence_signal(p)
        inference = _extract_inference_signal(p)
        transition = _extract_transition_signal(p)
        units.append(
            {
                "question": _infer_question(p),
                "method": _infer_method(p),
                "result": p[:300],
                "reasoning": f"Evidence: {evidence}; Inference: {inference}",
                "transition": transition,
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
        "reasoning_chain": [_extract_reasoning_chain(discussion_text)],
    }


def _infer_question(text: str) -> str:
    low = text.lower()
    if "association" in low or "correlat" in low:
        return "Does the study support an association between factors?"
    if "increase" in low or "decrease" in low or "improve" in low:
        return "Does the intervention/exposure change the target outcome?"
    return "What does this result attempt to test?"


def _infer_method(text: str) -> str:
    low = text.lower()
    if "randomized" in low or "trial" in low:
        return "Randomized trial-like evidence"
    if "cohort" in low:
        return "Cohort-style observational evidence"
    if "meta-analysis" in low:
        return "Meta-analysis style evidence synthesis"
    return "Method placeholder (rule-based extraction)"


def _extract_evidence_signal(text: str) -> str:
    low = text.lower()
    if "p<" in low or "p <" in low or "confidence interval" in low or "ci" in low:
        return "statistical signal detected"
    if "significant" in low:
        return "significance wording detected"
    if "observed" in low or "showed" in low:
        return "observational wording detected"
    return "limited explicit evidence signal"


def _extract_inference_signal(text: str) -> str:
    low = text.lower()
    if "suggest" in low or "indicate" in low:
        return "causal/interpretive inference candidate"
    if "may" in low or "might" in low or "could" in low:
        return "uncertain inference candidate"
    return "direct inference not explicit"


def _extract_transition_signal(text: str) -> str:
    low = text.lower()
    if "furthermore" in low or "additionally" in low:
        return "Supports additive progression to next finding"
    if "however" in low or "in contrast" in low:
        return "Introduces contrast progression to next finding"
    return "Transition to next finding"


def _extract_reasoning_chain(text: str) -> str:
    low = text.lower()
    has_result = any(k in low for k in ["result", "finding", "observed", "showed"])
    has_mechanism = any(k in low for k in ["mechanism", "pathway", "biological"])
    has_literature = any(k in low for k in ["consistent with", "previous study", "prior study"])
    has_inference = any(k in low for k in ["therefore", "thus", "suggest", "indicate"])
    return (
        f"result={has_result}, mechanism={has_mechanism}, "
        f"literature={has_literature}, inference={has_inference}"
    )
