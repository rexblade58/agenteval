"""AgentEval - report rendering.

Produces machine-readable JSON and human-readable Markdown reports.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from .evaluator import EvaluationReport

SCHEMA_VERSION = 2


def to_dict(report: EvaluationReport) -> dict[str, Any]:
    """Convert a report into a plain serializable dict."""
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": report.provider,
        "model": report.model,
        "suite": report.suite,
        "total_tasks": report.total_tasks,
        "passed": report.passed,
        "failed": report.failed,
        "accuracy": round(report.accuracy, 4),
        "pass_at_1": round(report.pass_at_1, 4),
        "pass_at_k": round(report.pass_at_k, 4),
        "robustness": round(report.robustness, 4) if report.robustness is not None else None,
        "avg_latency_ms": round(report.avg_latency_ms, 2),
        "total_cost_usd": round(report.total_cost_usd, 6),
        "category_breakdown": {
            cat: {
                "total": int(entry["total"]),
                "passed": int(entry["passed"]),
                "accuracy": round(entry["accuracy"], 4),
            }
            for cat, entry in report.category_breakdown.items()
        },
        "results": [
            {
                "task_id": r.task_id,
                "category": r.category,
                "passed": r.passed,
                "latency_ms": round(r.latency_ms, 2),
                "attempts": r.attempts,
                "error": r.error,
            }
            for r in report.results
        ],
    }


def to_json(report: EvaluationReport, pretty: bool = True) -> str:
    """Serialize a report to JSON."""
    return json.dumps(to_dict(report), indent=2 if pretty else None)


def to_markdown(report: EvaluationReport) -> str:
    """Render a report as a readable Markdown table."""
    lines: list[str] = []
    lines.append(f"# AgentEval Report\n")
    lines.append(f"- **Provider:** {report.provider} (`{report.model}`)")
    lines.append(f"- **Suite:** {report.suite}")
    lines.append(f"- **Tasks:** {report.passed}/{report.total_tasks} passed")
    lines.append(f"- **Accuracy:** {report.accuracy:.1%}")
    if report.robustness is not None:
        lines.append(f"- **Robustness:** {report.robustness:.1%} (adversarial)")
    lines.append(f"- **Avg latency:** {report.avg_latency_ms:.1f} ms")
    lines.append(f"- **Total cost:** ${report.total_cost_usd:.6f}\n")

    if report.category_breakdown:
        lines.append("## Category breakdown\n")
        lines.append("| Category | Passed | Total | Accuracy |")
        lines.append("|----------|--------|-------|----------|")
        for cat, entry in sorted(report.category_breakdown.items()):
            lines.append(
                f"| {cat} | {int(entry['passed'])} | {int(entry['total'])} | {entry['accuracy']:.1%} |"
            )
        lines.append("")

    lines.append("## Task results\n")
    lines.append("| Task | Category | Result | Latency |")
    lines.append("|------|----------|--------|---------|")
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        if r.error:
            status += f" ({r.error[:40]})"
        lines.append(f"| {r.task_id} | {r.category} | {status} | {r.latency_ms:.0f} ms |")
    lines.append("")

    return "\n".join(lines)


__all__ = ["to_dict", "to_json", "to_markdown", "SCHEMA_VERSION"]
