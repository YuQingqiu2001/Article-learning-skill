"""AI review guard for post-learning bias checks.

v0.1 behavior:
- Runs immediately after each single-paper analysis.
- Uses conservative rule checks as a placeholder for real AI model verification.
- If potential bias is detected, emits human-facing questions.

TODO:
- Replace `simulate_ai_review` with real LLM/API verification.
"""
from __future__ import annotations

from typing import Any


def simulate_ai_review(analysis: dict[str, Any]) -> dict[str, Any]:
    """Simulate AI second-pass verification.

    Returns a review report with score, findings and whether human guidance is needed.
    """
    sections = analysis.get("detected_sections", [])
    quality = analysis.get("quality_flag", "low")
    paper_type = analysis.get("paper_type", "uncertain")
    patterns = analysis.get("patterns", {})

    issues: list[str] = []
    score = 1.0

    if paper_type == "uncertain":
        issues.append("Paper type remains uncertain after first-pass learning")
        score -= 0.35

    if quality == "low":
        issues.append("PDF extraction quality is low; learned knowledge may be noisy")
        score -= 0.35

    if len(sections) < 2:
        issues.append("Too few structural sections detected")
        score -= 0.20

    has_any_pattern = any(bool(v) for v in patterns.values()) if isinstance(patterns, dict) else False
    if not has_any_pattern:
        issues.append("No stable writing pattern extracted")
        score -= 0.15

    score = max(0.0, round(score, 3))
    needs_human = score < 0.65 or bool(issues)

    questions: list[str] = []
    if needs_human:
        questions = [
            "该文献优先学习方向是什么？（机制/方法/写作结构/临床意义）",
            "若当前类型判断不准，请人工指定是 Article 还是 Review。",
            "哪些结论应标记为 uncertain 并暂缓沉淀到 skills？",
        ]

    return {
        "agreement_score": score,
        "issues": issues,
        "needs_human_guidance": needs_human,
        "questions": questions,
    }
