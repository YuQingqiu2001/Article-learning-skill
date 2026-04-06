"""Extract reusable writing patterns."""
from __future__ import annotations

from typing import Any


def abstract_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    patterns: list[dict[str, str]] = []
    if analysis.get("paper_type") == "article":
        patterns.append({"pattern": "Background -> Objective -> Methods -> Results -> Conclusion", "confidence": "high"})
    elif analysis.get("paper_type") == "review":
        patterns.append({"pattern": "Background -> Scope -> Evidence synthesis -> Perspective", "confidence": "high"})
    return patterns


def results_logic_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    if analysis.get("paper_type") != "article":
        return []
    findings = analysis.get("parsed", {}).get("results_finding_units", [])
    reasoning_rich = any("Evidence:" in str(f.get("reasoning", "")) for f in findings)
    base = {"pattern": "Question -> Method -> Result -> Reasoning -> Transition", "confidence": "high"}
    if reasoning_rich:
        return [
            base,
            {"pattern": "Evidence signal -> Inference statement -> Next experiment transition", "confidence": "medium"},
        ]
    return [base]


def review_structure_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    if analysis.get("paper_type") != "review":
        return []
    org = analysis.get("parsed", {}).get("organization_type", "mixed")
    return [
        {"pattern": f"{org}: Claim -> Evidence -> Synthesis", "confidence": "medium"},
        {"pattern": f"{org}: Claim -> Counterpoint -> Integration -> Perspective", "confidence": "medium"},
    ]


def scientific_phrases(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Generalized phrase templates (entity-stripped placeholders)."""
    return [
        {"category": "描述结果", "phrase": "The intervention was associated with a significant improvement in [outcome]."},
        {"category": "表达因果", "phrase": "These findings suggest that [mechanism] may drive [phenotype]."},
        {"category": "引用文献", "phrase": "Consistent with prior studies, our observations support [claim]."},
        {"category": "提出假设", "phrase": "We hypothesize that [factor] mediates the observed association."},
        {"category": "强调局限性", "phrase": "This interpretation should be considered in light of [limitation]."},
        {"category": "指出研究意义", "phrase": "Our work provides a framework for future studies targeting [problem]."},
    ]
