"""Human feedback ingestion for iterative skill evolution.

Feedback file format (JSON):
{
  "paper_a.pdf": {
    "paper_type": "review",
    "learn_focus": "mechanism",
    "allow_deposit": true,
    "notes": "Focus on claim-evidence-synthesis"
  }
}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


VALID_TYPES = {"article", "review", "uncertain"}


def load_feedback_map(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    except json.JSONDecodeError:
        return {}
    return {}


def apply_feedback(analysis: dict[str, Any], feedback: dict[str, Any]) -> dict[str, Any]:
    """Apply human feedback into one-paper analysis result."""
    if not feedback:
        return analysis

    updated = dict(analysis)
    notes: list[str] = list(updated.get("human_notes", []))

    ptype = feedback.get("paper_type")
    if isinstance(ptype, str) and ptype in VALID_TYPES:
        updated["paper_type"] = ptype
        notes.append(f"paper_type_overridden:{ptype}")

    learn_focus = feedback.get("learn_focus")
    if isinstance(learn_focus, str) and learn_focus.strip():
        updated["learn_focus"] = learn_focus.strip()

    if feedback.get("allow_deposit") is True and updated.get("status") != "ok":
        notes.append(f"allow_deposit_by_human:prev_status={updated['status']}")
        updated["status"] = "ok"

    extra = feedback.get("notes")
    if isinstance(extra, str) and extra.strip():
        notes.append(extra.strip())

    if notes:
        updated["human_notes"] = notes
    return updated
