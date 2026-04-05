"""Parser for Review papers."""
from __future__ import annotations

import re
from typing import Any


REVIEW_KEYS = ["abstract", "introduction", "conclusion"]

# Organization type keywords with weights.
_ORG_KEYWORDS: dict[str, list[str]] = {
    "mechanism-based": ["mechanism", "pathway", "signaling", "molecular", "receptor"],
    "disease-based": ["disease", "syndrome", "disorder", "clinical features", "epidemiology"],
    "method-based": ["method", "technique", "approach", "protocol", "assay", "tool"],
    "timeline-based": ["history", "timeline", "evolution", "milestone", "decade", "era"],
}


def parse_review_structure(text: str, section_map: dict[str, str], headers: list[str]) -> dict[str, Any]:
    """Extract review-specific structure with improved content analysis."""
    org_types = detect_organization_types(text, headers)
    claim_evidence_synthesis = build_ces_from_content(section_map, headers)

    high_level = extract_high_level_writing(section_map)

    return {
        "sections": {k: section_map.get(k, "")[:2000] for k in REVIEW_KEYS},
        "main_sections": headers[:12],
        "organization_type": org_types[0] if org_types else "mixed",
        "organization_types_detected": org_types,
        "claim_evidence_synthesis": claim_evidence_synthesis,
        "high_level_writing": high_level,
    }


def detect_organization_types(text: str, headers: list[str]) -> list[str]:
    """Detect all matching organization types, ranked by relevance."""
    combined = (text[:3000] + " " + " ".join(headers)).lower()
    scores: dict[str, int] = {}
    for org_type, keywords in _ORG_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in combined)
        if score > 0:
            scores[org_type] = score

    if not scores:
        return ["mixed"]

    # Return all detected types sorted by score descending
    return sorted(scores, key=scores.get, reverse=True)


def build_ces_from_content(section_map: dict[str, str], headers: list[str]) -> list[dict[str, str]]:
    """Build claim-evidence-synthesis triples from body sections."""
    # Gather body text from non-standard sections (the review's thematic sections)
    body_sections = {k: v for k, v in section_map.items() if k not in ("body", "abstract", "introduction", "conclusion") and v.strip()}

    ces: list[dict[str, str]] = []

    if body_sections:
        for section_name, content in list(body_sections.items())[:5]:
            # Try to find claim-like sentences (first 1-2 sentences often state the theme)
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", content) if s.strip()]
            claim = sentences[0][:200] if sentences else ""
            evidence = " ".join(sentences[1:4])[:300] if len(sentences) > 1 else ""
            # Look for synthesis-like sentences (conclusions, summaries)
            synth_candidates = [s for s in sentences if any(kw in s.lower() for kw in ["overall", "together", "thus", "therefore", "in summary", "suggest"])]
            synthesis = synth_candidates[0][:200] if synth_candidates else (sentences[-1][:200] if sentences else "")
            ces.append({"section": section_name, "claim": claim, "evidence": evidence, "synthesis": synthesis})
    else:
        # Fallback: use introduction and conclusion
        intro = section_map.get("introduction", "")[:300]
        concl = section_map.get("conclusion", "")[:300]
        if intro or concl:
            ces.append({"section": "main", "claim": intro, "evidence": "", "synthesis": concl})

    return ces


def extract_high_level_writing(section_map: dict[str, str]) -> dict[str, str]:
    """Extract knowledge gap, future directions, and clinical implications from text."""
    conclusion = section_map.get("conclusion", "")
    intro = section_map.get("introduction", "")
    combined = intro + " " + conclusion

    # Knowledge gap: sentences with gap/unclear/unknown/poorly understood
    gap_matches = re.findall(r"[^.]*(?:gap|unclear|unknown|poorly understood|remain(?:s)? elusive|not (?:well |fully )?understood)[^.]*\.", combined, re.IGNORECASE)
    knowledge_gap = gap_matches[0].strip()[:300] if gap_matches else ""

    # Future directions
    future_matches = re.findall(r"[^.]*(?:future (?:stud|research|work|direction)|warrant(?:s|ed)? further|further investigation|need(?:s|ed)? to be explored)[^.]*\.", combined, re.IGNORECASE)
    future_directions = future_matches[0].strip()[:300] if future_matches else ""

    # Clinical implications
    clin_matches = re.findall(r"[^.]*(?:clinical (?:implication|relevance|significance|application)|translat|therapeutic potential|treatment strateg)[^.]*\.", combined, re.IGNORECASE)
    clinical_implications = clin_matches[0].strip()[:300] if clin_matches else ""

    return {
        "knowledge_gap": knowledge_gap,
        "future_directions": future_directions,
        "clinical_implications": clinical_implications,
    }
