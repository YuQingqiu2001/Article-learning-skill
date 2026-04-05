"""Conservative knowledge extractor with improved confidence logic and uncertainty tagging."""
from __future__ import annotations

import re
from typing import Any


# Knowledge categories with their detection keywords and base confidence per paper type.
# Keywords use word-boundary matching to avoid substring false positives.
_KNOWLEDGE_RULES: list[tuple[str, str, list[str]]] = [
    ("新机制或通路", "Potential mechanism/pathway discussed", ["pathway", "mechanism", "signaling", "signal transduction"]),
    ("基因或分子", "Potential gene/molecular factor reported", ["gene expression", "genes", "protein", "molecular", "receptor", "enzyme"]),
    ("研究方法", "Study design pattern detected", ["randomized", "cohort", "meta-analysis", "cross-sectional", "case-control"]),
    ("生物标志物", "Potential biomarker reported", ["biomarker", "marker", "predictor", "indicator"]),
    ("药物靶点", "Drug target or therapeutic agent discussed", ["drug target", "inhibitor", "agonist", "antagonist", "therapeutic"]),
]

# Per-paper-type confidence mapping.
# Reviews synthesize multiple sources -> medium confidence.
# Articles report primary data -> medium for strong matches, low for weak.
_CONFIDENCE_MAP = {
    "review": {"base": "medium", "multi_hit": "medium"},
    "article": {"base": "low", "multi_hit": "medium"},
    "uncertain": {"base": "low", "multi_hit": "low"},
}


def extract_knowledge(text: str, paper_type: str) -> list[dict[str, Any]]:
    """Extract knowledge items with proper confidence differentiation."""
    low = text.lower()
    items: list[dict[str, Any]] = []
    conf_map = _CONFIDENCE_MAP.get(paper_type, _CONFIDENCE_MAP["uncertain"])

    for kind, summary, keywords in _KNOWLEDGE_RULES:
        hits = sum(1 for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", low))
        if hits == 0:
            continue
        confidence = conf_map["multi_hit"] if hits >= 2 else conf_map["base"]
        stability = "cautious" if confidence == "medium" else "contested"
        items.append({
            "type": kind,
            "summary": summary,
            "stability": stability,
            "confidence": confidence,
            "uncertain": confidence == "low",
            "keyword_hits": hits,
        })

    if paper_type == "review" and not items:
        # Reviews always contribute at least a trend signal
        items.append({
            "type": "研究趋势",
            "summary": "Review-level trend synthesis candidate",
            "stability": "cautious",
            "confidence": "medium",
            "uncertain": False,
            "keyword_hits": 0,
        })

    return items
