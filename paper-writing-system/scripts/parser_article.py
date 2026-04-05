"""Parser for Original Article style papers."""
from __future__ import annotations

import re
from typing import Any


SECTION_KEYS = ["abstract", "introduction", "methods", "results", "discussion"]

# Semantic cue words for abstract sentence role detection.
_ROLE_CUES: list[tuple[str, list[str]]] = [
    ("Background", [
        "background", "currently", "recent studies", "it is known", "emerging",
        "increasing", "prevalence", "has been", "remains", "growing",
    ]),
    ("Objective", [
        "aim", "objective", "purpose", "goal", "sought to", "investigated",
        "aimed", "this study", "we examined", "we evaluated", "hypothesize",
        "determine whether", "assess the",
    ]),
    ("Methods", [
        "method", "design", "participant", "sample", "recruited", "performed",
        "analyzed", "measured", "collected", "randomized", "retrospective",
        "prospective", "enrolled", "protocol", "experiment",
    ]),
    ("Results", [
        "result", "found", "showed", "demonstrated", "observed", "significant",
        "increased", "decreased", "associated", "correlated", "p <", "p=",
        "confidence interval", "odds ratio", "hazard ratio",
    ]),
    ("Conclusion", [
        "conclusion", "conclude", "suggest", "implication", "in summary",
        "taken together", "these findings", "our data", "overall",
        "this study demonstrates", "future", "recommend",
    ]),
]


def parse_article_structure(text: str, section_map: dict[str, str]) -> dict[str, Any]:
    """Extract article-specific structure with improved semantic parsing."""
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
    """Label abstract sentences using semantic cues instead of positional mapping."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", abstract) if s.strip()]
    if not sentences:
        return []

    tagged: list[dict[str, str]] = []
    last_label_idx = -1  # Track ordering to prefer forward progression

    for sent in sentences:
        sent_lower = sent.lower()
        best_label = None
        best_score = 0

        for role_idx, (role, cues) in enumerate(_ROLE_CUES):
            score = sum(1 for cue in cues if cue in sent_lower)
            # Bonus for maintaining forward progression of roles
            if role_idx > last_label_idx:
                score += 0.5
            if score > best_score:
                best_score = score
                best_label = role
                best_label_idx = role_idx

        if best_label is None or best_score < 0.5:
            # Fallback: infer from position in abstract
            position_ratio = len(tagged) / max(len(sentences), 1)
            if position_ratio < 0.2:
                best_label = "Background"
            elif position_ratio < 0.4:
                best_label = "Objective"
            elif position_ratio < 0.6:
                best_label = "Methods"
            elif position_ratio < 0.8:
                best_label = "Results"
            else:
                best_label = "Conclusion"
        else:
            last_label_idx = best_label_idx

        tagged.append({"label": best_label, "sentence": sent})
    return tagged


def split_findings(results_text: str) -> list[dict[str, str]]:
    """Split results into finding units with basic content extraction."""
    if not results_text.strip():
        return []

    # Split on paragraph breaks or sentences starting with common result starters
    parts = [p.strip() for p in re.split(r"\n\s*\n|(?<=\.)\s+(?=We |Our |These |This |The |Figure |Table |As shown )", results_text) if p.strip()]

    units: list[dict[str, str]] = []
    for p in parts[:8]:  # Allow up to 8 finding units
        result_snippet = p[:400]
        # Try to detect method mention within finding
        method_match = re.search(r"(?:using|by|via|with|through)\s+(.{10,80}?)(?:\.|,)", p, re.IGNORECASE)
        method = method_match.group(1).strip() if method_match else ""

        # Try to detect reasoning/interpretation
        reason_match = re.search(r"(?:suggest|indicat|demonstrat|confirm|impl)\w+\s+(?:that\s+)?(.{10,120}?)(?:\.|$)", p, re.IGNORECASE)
        reasoning = reason_match.group(0).strip() if reason_match else ""

        units.append(
            {
                "result": result_snippet,
                "method": method,
                "reasoning": reasoning,
            }
        )
    return units


def extract_discussion_modes(discussion_text: str) -> dict[str, list[str]]:
    """Extract discussion modes with evidence snippets."""
    if not discussion_text:
        return {
            "causal_explanation": [],
            "comparative": [],
            "limitations": [],
            "biological_significance": [],
            "clinical_significance": [],
        }

    lower = discussion_text.lower()
    modes: dict[str, list[str]] = {}

    # Causal explanation
    causal_matches = re.findall(r"[^.]*(?:because|suggest(?:s|ing)?|indicat(?:e|es|ing)|explain(?:s|ed)?|due to)[^.]*\.", discussion_text, re.IGNORECASE)
    modes["causal_explanation"] = [m.strip()[:200] for m in causal_matches[:3]]

    # Comparative
    comp_matches = re.findall(r"[^.]*(?:consistent with|in (?:contrast|line) with|compared (?:with|to)|similar(?:ly)?|unlike)[^.]*\.", discussion_text, re.IGNORECASE)
    modes["comparative"] = [m.strip()[:200] for m in comp_matches[:3]]

    # Limitations
    lim_matches = re.findall(r"[^.]*(?:limitation|caveat|drawback|caution|acknowledge)[^.]*\.", discussion_text, re.IGNORECASE)
    modes["limitations"] = [m.strip()[:200] for m in lim_matches[:3]]

    # Biological significance
    bio_matches = re.findall(r"[^.]*(?:mechanism|pathway|molecular|cellular|physiolog)[^.]*\.", discussion_text, re.IGNORECASE)
    modes["biological_significance"] = [m.strip()[:200] for m in bio_matches[:3]]

    # Clinical significance
    clin_matches = re.findall(r"[^.]*(?:clinical|therapeutic|treatment|patient|prognos)[^.]*\.", discussion_text, re.IGNORECASE)
    modes["clinical_significance"] = [m.strip()[:200] for m in clin_matches[:3]]

    return modes
