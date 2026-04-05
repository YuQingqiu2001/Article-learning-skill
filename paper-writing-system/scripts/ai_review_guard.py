"""AI review guard for post-learning bias checks.

v0.2 behavior:
- Runs immediately after each single-paper analysis.
- Uses improved rule-based scoring with calibrated thresholds.
- Only flags for human guidance when multiple issues compound.

TODO:
- Replace with real LLM/API verification for production use.
"""
from __future__ import annotations

from typing import Any


def simulate_ai_review(analysis: dict[str, Any]) -> dict[str, Any]:
    """Simulate AI second-pass verification with calibrated scoring.

    Returns a review report with score, findings and whether human guidance is needed.
    Score starts at 1.0 and is reduced by detected issues proportionally.
    Human guidance is only triggered when the score drops below threshold.
    """
    sections = analysis.get("detected_sections", [])
    quality = analysis.get("quality_flag", "low")
    paper_type = analysis.get("paper_type", "uncertain")
    patterns = analysis.get("patterns", {})
    knowledge = analysis.get("knowledge", [])

    issues: list[str] = []
    score = 1.0

    # Uncertain type is a moderate concern, not critical alone
    if paper_type == "uncertain":
        issues.append("Paper type remains uncertain after first-pass classification")
        score -= 0.25

    # Low quality extraction is a significant concern
    if quality == "low":
        issues.append("PDF extraction quality is low; learned knowledge may be noisy")
        score -= 0.30
    elif quality == "medium":
        # Medium quality is acceptable, minor deduction
        score -= 0.05

    # Structural completeness
    if len(sections) < 2:
        issues.append("Too few structural sections detected")
        score -= 0.15

    # Pattern extraction check
    has_any_pattern = False
    if isinstance(patterns, dict):
        has_any_pattern = any(
            isinstance(v, list) and len(v) > 0
            for v in patterns.values()
        )
    if not has_any_pattern:
        issues.append("No writing pattern extracted from this paper")
        score -= 0.10

    # Knowledge extraction check: all items marked uncertain is a concern
    if knowledge and all(k.get("uncertain") for k in knowledge):
        issues.append("All extracted knowledge items are marked uncertain")
        score -= 0.10

    score = max(0.0, round(score, 3))

    # Only request human guidance for genuinely problematic papers.
    # Threshold 0.50 means at least two significant issues must compound.
    needs_human = score < 0.50

    questions: list[str] = []
    if needs_human:
        # Generate targeted questions based on actual issues
        if paper_type == "uncertain":
            questions.append("请人工指定该文献是 Article 还是 Review。")
        if quality == "low":
            questions.append("PDF提取质量低，是否需要重新获取该文献或手动补充关键信息？")
        if len(sections) < 2:
            questions.append("检测到的章节极少，该文献是否为完整论文？")
        questions.append("该文献优先学习方向是什么？（机制/方法/写作结构/临床意义）")

    return {
        "agreement_score": score,
        "issues": issues,
        "needs_human_guidance": needs_human,
        "questions": questions,
    }
