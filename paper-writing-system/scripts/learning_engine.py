"""Human-like learning evolution engine.

This module simulates a conservative "read -> summarize -> reinforce -> update confidence"
loop so the skill can evolve gradually instead of one-shot extraction.

Confidence thresholds:
- observing: seen 1 time (initial observation)
- candidate: seen >= 2 times (pattern begins to repeat)
- high_conf: seen >= 3 times AND weighted_score >= 3.5
  (ensures both repetition and quality evidence before promoting)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class PatternCandidate:
    category: str
    text: str
    source: str
    confidence: str
    paper_type: str
    quality_flag: str


def _default_state() -> dict[str, Any]:
    return {
        "version": "0.2",
        "patterns": {},
        "history": [],
    }


def load_learning_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _default_state()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_state()


def save_learning_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pattern_key(category: str, text: str) -> str:
    return f"{category}::{text.strip().lower()}"


def paper_weight(paper_type: str, quality_flag: str) -> float:
    """Calculate weight for a paper's contribution to pattern confidence.

    Balanced so that both reviews and articles can reach high_conf in
    a comparable number of exposures:
    - review + high quality  = 1.0 + 0.4 + 0.5 = 1.9
    - article + high quality = 1.0 + 0.0 + 0.5 = 1.5
    - review + medium        = 1.0 + 0.4 + 0.2 = 1.6
    - article + medium       = 1.0 + 0.0 + 0.2 = 1.2

    With threshold 3.5: reviews need ~2 high-quality papers, articles need ~3.
    """
    weight = 1.0
    if paper_type == "review":
        weight += 0.4
    if quality_flag == "high":
        weight += 0.5
    elif quality_flag == "medium":
        weight += 0.2
    elif quality_flag == "low":
        weight -= 0.3
    return max(0.1, weight)


def update_learning_state(state: dict[str, Any], candidates: list[PatternCandidate], date_str: str) -> dict[str, Any]:
    patterns = state.setdefault("patterns", {})
    today_updates: list[dict[str, Any]] = []

    for c in candidates:
        key = pattern_key(c.category, c.text)
        record = patterns.get(
            key,
            {
                "category": c.category,
                "text": c.text,
                "first_seen": date_str,
                "last_seen": date_str,
                "count": 0,
                "weighted_score": 0.0,
                "status": "observing",
                "sources": [],
            },
        )

        w = paper_weight(c.paper_type, c.quality_flag)
        record["count"] += 1
        record["weighted_score"] = round(float(record["weighted_score"]) + w, 3)
        record["last_seen"] = date_str
        if c.source not in record["sources"]:
            record["sources"].append(c.source)

        # Confidence evolution: requires both repeated exposure and sufficient evidence weight.
        if record["count"] >= 3 and record["weighted_score"] >= 3.5:
            record["status"] = "high_conf"
        elif record["count"] >= 2:
            record["status"] = "candidate"
        else:
            record["status"] = "observing"

        patterns[key] = record
        today_updates.append({"key": key, "status": record["status"], "count": record["count"]})

    state.setdefault("history", []).append({"date": date_str, "updates": today_updates})
    # Keep history bounded to 50 entries for longer-term tracking.
    state["history"] = state["history"][-50:]
    return state


def extract_focus_items(state: dict[str, Any], top_k: int = 5) -> list[dict[str, Any]]:
    """Select what to focus next day: uncertain and high-value items first.

    Priority: items still in 'observing' status with higher weighted_score
    are prime candidates for reinforcement.
    """
    values = list(state.get("patterns", {}).values())
    values.sort(key=lambda x: (x.get("status") != "observing", x.get("weighted_score", 0.0)), reverse=True)
    return values[:top_k]
