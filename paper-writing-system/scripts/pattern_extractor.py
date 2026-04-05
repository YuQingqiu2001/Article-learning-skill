"""Extract reusable writing patterns from actual paper content."""
from __future__ import annotations

import re
from typing import Any


def abstract_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Extract the actual abstract role sequence from parsed data."""
    patterns: list[dict[str, str]] = []
    parsed = analysis.get("parsed", {})
    roles = parsed.get("abstract_roles", [])

    if roles:
        # Build the actual observed sequence from the paper's abstract
        sequence = " -> ".join(dict.fromkeys(r["label"] for r in roles))  # deduplicated, ordered
        if sequence:
            patterns.append({"pattern": sequence, "confidence": "high" if len(roles) >= 3 else "medium"})

    # Fallback generic patterns if no roles were parsed
    if not patterns:
        if analysis.get("paper_type") == "article":
            patterns.append({"pattern": "Background -> Objective -> Methods -> Results -> Conclusion", "confidence": "low"})
        elif analysis.get("paper_type") == "review":
            patterns.append({"pattern": "Background -> Scope -> Evidence synthesis -> Perspective", "confidence": "low"})

    return patterns


def results_logic_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Extract results logic patterns from the actual finding units."""
    if analysis.get("paper_type") != "article":
        return []

    parsed = analysis.get("parsed", {})
    findings = parsed.get("results_finding_units", [])
    if not findings:
        return [{"pattern": "Question -> Method -> Result -> Reasoning -> Transition", "confidence": "low"}]

    patterns: list[dict[str, str]] = []
    # Analyze what components are actually present in the findings
    has_method = any(f.get("method") for f in findings)
    has_reasoning = any(f.get("reasoning") for f in findings)
    n_findings = len(findings)

    components = ["Result"]
    if has_method:
        components.insert(0, "Method")
    if has_reasoning:
        components.append("Reasoning")
    if n_findings > 1:
        components.append("Transition")

    sequence = " -> ".join(components)
    confidence = "high" if has_method and has_reasoning else "medium" if (has_method or has_reasoning) else "low"
    patterns.append({"pattern": sequence, "confidence": confidence})

    return patterns


def review_structure_patterns(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Extract review structure patterns from actual CES analysis."""
    if analysis.get("paper_type") != "review":
        return []

    parsed = analysis.get("parsed", {})
    org_types = parsed.get("organization_types_detected", [])
    org = org_types[0] if org_types else parsed.get("organization_type", "mixed")
    ces = parsed.get("claim_evidence_synthesis", [])

    # Evaluate quality of CES extraction
    has_real_content = any(item.get("claim") and item.get("synthesis") for item in ces)
    confidence = "high" if has_real_content and len(ces) >= 2 else "medium" if has_real_content else "low"

    patterns = [{"pattern": f"{org}: Claim -> Evidence -> Synthesis", "confidence": confidence}]

    # If multiple org types detected, note the secondary pattern
    if len(org_types) > 1:
        patterns.append({"pattern": f"secondary:{org_types[1]}", "confidence": "low"})

    return patterns


def scientific_phrases(analysis: dict[str, Any]) -> list[dict[str, str]]:
    """Extract actual sentence templates from the paper by generalizing entities."""
    parsed = analysis.get("parsed", {})
    sections = parsed.get("sections", {})
    phrases: list[dict[str, str]] = []

    # Category -> (section_key, sentence_pattern_to_find)
    _PHRASE_EXTRACTORS: list[tuple[str, str, re.Pattern[str]]] = [
        ("描述结果", "results", re.compile(r"([^.]*(?:associated with|correlated with|significantly|demonstrated|revealed)[^.]{10,}\.)", re.IGNORECASE)),
        ("表达因果", "discussion", re.compile(r"([^.]*(?:suggest(?:s|ing)? that|indicate(?:s|d)? that|imply|due to|because)[^.]{10,}\.)", re.IGNORECASE)),
        ("引用文献", "discussion", re.compile(r"([^.]*(?:consistent with|in (?:line|agreement) with|previous(?:ly)?|prior stud)[^.]{10,}\.)", re.IGNORECASE)),
        ("强调局限性", "discussion", re.compile(r"([^.]*(?:limitation|should be (?:interpreted|considered)|caveat|caution)[^.]{10,}\.)", re.IGNORECASE)),
        ("指出研究意义", "conclusion", re.compile(r"([^.]*(?:provide(?:s)? (?:a |new |novel )?(?:framework|insight|evidence)|important|implications)[^.]{10,}\.)", re.IGNORECASE)),
    ]

    for category, section_key, pattern in _PHRASE_EXTRACTORS:
        text = sections.get(section_key, "")
        if not text:
            continue
        match = pattern.search(text)
        if match:
            raw = match.group(1).strip()
            # Generalize entities: replace specific terms with [entity] placeholders
            generalized = _generalize_phrase(raw)
            if len(generalized) > 20:
                phrases.append({"category": category, "phrase": generalized})

    # If no content-derived phrases, return a minimal set of generic templates
    if not phrases:
        phrases = [
            {"category": "描述结果", "phrase": "The intervention was associated with a significant improvement in [outcome]."},
            {"category": "表达因果", "phrase": "These findings suggest that [mechanism] may drive [phenotype]."},
        ]

    return phrases


def _generalize_phrase(sentence: str) -> str:
    """Replace specific entities with generalized placeholders."""
    s = sentence
    # Replace numeric values
    s = re.sub(r"\b\d+\.?\d*\s*%", "[percentage]", s)
    s = re.sub(r"(?:p\s*[<>=]\s*)\d+\.?\d*", "[p-value]", s)
    s = re.sub(r"\b\d+\.?\d*\s*(?:mg|kg|ml|μg|ng|mmol|μmol|cm|mm)\b", "[measurement]", s, flags=re.IGNORECASE)
    return s
