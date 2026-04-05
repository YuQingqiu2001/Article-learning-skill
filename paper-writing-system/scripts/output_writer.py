"""Markdown writers for memory, skill patterns, and generated examples."""
from __future__ import annotations

from pathlib import Path
import re
from typing import Any


def write_daily_memory(memory_file: Path, date_str: str, analyses: list[dict[str, Any]], message: str | None = None) -> None:
    memory_file.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Daily Memory - {date_str}", ""]

    if message:
        lines.extend([f"- {message}", ""])

    if analyses:
        lines.append("## Processed Papers")
        for a in analyses:
            lines.append(f"- `{a['file_name']}` | type={a['paper_type']} | quality={a['quality_flag']}")
        lines.append("")

        lines.append("## Per-paper Structure Summary")
        for a in analyses:
            lines.append(f"### {a['file_name']}")
            lines.append(f"- Type: {a['paper_type']}")
            lines.append(f"- Key sections: {', '.join(a.get('detected_sections', [])) or 'N/A'}")
            lines.append(f"- Learned writing patterns: {', '.join(a.get('pattern_brief', [])) or 'N/A'}")
        lines.append("")

        lines.append("## Daily Writing Capability Summary")
        lines.append("- SCI phrase patterns: generalized reusable sentence functions")
        lines.append("- Abstract structure: role-based sequence extraction")
        lines.append("- Results progression: finding-unit chain modeling")
        lines.append("- Review integration logic: claim-evidence-synthesis abstraction")
        lines.append("")

        lines.append("## Daily Research Thinking Summary")
        lines.append("- Problem framing: from gap to testable question")
        lines.append("- Experiment path: method-result-reasoning consistency")
        lines.append("- Review cognition: integrating consensus, controversy and directions")

    memory_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_unique_bullets(target: Path, heading: str, bullets: list[str]) -> None:
    """Append bullets with semantic de-duplication.

    If only source differs (same pattern text), keep one line to avoid memory inflation.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        target.write_text(f"# {heading}\n\n", encoding="utf-8")

    content = target.read_text(encoding="utf-8")
    existing_lines = [line.strip() for line in content.splitlines() if line.strip().startswith("-")]

    def canonical(line: str) -> str:
        base = re.sub(r"\s*\(source:.*?\)\s*$", "", line)
        return re.sub(r"\s+", " ", base).strip().lower()

    existing_keys = {canonical(x.removeprefix("- ")) for x in existing_lines}
    new_lines = []
    for b in bullets:
        key = canonical(b)
        if key not in existing_keys:
            new_lines.append(f"- {b}")
            existing_keys.add(key)

    if new_lines:
        with target.open("a", encoding="utf-8") as f:
            f.write("\n".join(new_lines) + "\n")


def write_generated_examples(target: Path, date_str: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Generated Examples - {date_str}",
        "",
        "## Original Article Style",
        "### Abstract",
        "Background: [Context gap].",
        "Objective: This study aimed to evaluate [core mechanism] in [target condition].",
        "Methods: We used [design] with [analysis strategy] to test [hypothesis].",
        "Results: We observed [finding 1], followed by [finding 2] that explained [variance].",
        "Conclusion: These data support a plausible role for [mechanism] in [outcome].",
        "",
        "### Results",
        "Result1 established the baseline association; Result2 validated robustness; Result3 clarified boundary conditions.",
        "",
        "### Discussion",
        "We connected findings to mechanism, contrasted prior reports, then bounded inference with limitations.",
        "",
        "## Review Style",
        "### Introduction",
        "We define the field-level problem, summarize fragmented evidence, and set synthesis objectives.",
        "",
        "### A Review Subsection",
        "Claim: [Theme] drives [phenomenon]. Evidence: multi-source studies converge on [point]. Synthesis: effect differs by context.",
        "",
        "### Conclusion",
        "We summarize consensus, identify knowledge gaps, propose future directions, and discuss clinical implications.",
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_evolution_log(target: Path, date_str: str, new_items: list[str], reinforced_items: list[str], uncertain_items: list[str], focus_items: list[dict[str, Any]]) -> None:
    """Write human-like daily reflection log for capability evolution."""
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Evolution Log - {date_str}", "", "## What I learned today"]
    if new_items:
        lines.extend([f"- {x}" for x in new_items[:10]])
    else:
        lines.append("- No strong new pattern observed.")

    lines.extend(["", "## What got reinforced"])
    if reinforced_items:
        lines.extend([f"- {x}" for x in reinforced_items[:10]])
    else:
        lines.append("- No pattern crossed reinforcement threshold today.")

    lines.extend(["", "## What remains uncertain"])
    if uncertain_items:
        lines.extend([f"- {x}" for x in uncertain_items[:10]])
    else:
        lines.append("- No major uncertain item captured.")

    lines.extend(["", "## Next learning focus (human-like priority)"])
    if focus_items:
        for item in focus_items:
            lines.append(f"- [{item.get('status')}] {item.get('text')} | score={item.get('weighted_score')} | seen={item.get('count')}")
    else:
        lines.append("- Continue collecting high-quality review papers.")

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")



def write_human_questions(target: Path, date_str: str, entries: list[dict[str, Any]]) -> None:
    """Write questions for human guidance when AI review detects potential bias."""
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Human Guidance Needed - {date_str}", ""]
    if not entries:
        lines.append("- No bias flagged today.")
    else:
        for e in entries:
            lines.append(f"## {e.get('file_name', 'unknown.pdf')}")
            lines.append(f"- Agreement score: {e.get('agreement_score')}")
            lines.append("- Issues:")
            for issue in e.get('issues', []):
                lines.append(f"  - {issue}")
            lines.append("- Questions for human:")
            for q in e.get('questions', []):
                lines.append(f"  - {q}")
            lines.append("")

    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
