"""AgentEval - human-in-the-loop review.

Automatic checkers (contains/semantic) can miss nuance. The review flow
lets a human audit failed tasks and re-score the report:

1. `agenteval run --review review.jsonl` writes a review queue containing
   every failed task (prompt, reference, model output).
2. The human edits the queue, or runs `agenteval review review.jsonl
   --interactive` to judge each item as pass / fail / skip.
3. `agenteval review review.jsonl --apply` merges the judgments back into
   the report and prints the updated score.

Queue file format (JSONL):
- first line:  {"meta": {...}}        - original report context
- later lines: {"task_id": ..., "status": "pending"} - one per failed task
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluator import EvaluationReport


@dataclass
class ReviewEntry:
    """One failed task awaiting a human judgment."""

    task_id: str
    category: str
    prompt: str
    reference: str
    output: str
    status: str = "pending"  # pending | pass | fail | skip


def write_review_queue(path: Path, report: EvaluationReport) -> int:
    """Write failed tasks to a review queue file. Returns the count written."""
    failed = [r for r in report.results if not r.passed and r.task_id]
    meta = {
        "provider": report.provider,
        "model": report.model,
        "suite": report.suite,
        "total_tasks": report.total_tasks,
        "passed": report.passed,
        "schema_version": 3,
    }
    lines = [json.dumps({"meta": meta})]
    for r in failed:
        lines.append(json.dumps({
            "task_id": r.task_id,
            "category": r.category,
            "prompt": r.prompt,
            "reference": r.reference,
            "output": r.output,
            "status": "pending",
        }))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(failed)


def load_review_queue(path: Path) -> tuple[dict[str, Any], list[ReviewEntry]]:
    """Load the queue. Returns (meta, entries)."""
    if not path.is_file():
        raise FileNotFoundError(f"review queue not found: {path}")
    meta: dict[str, Any] = {}
    entries: list[ReviewEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "meta" in data:
            meta = data["meta"]
        else:
            entries.append(ReviewEntry(
                task_id=data.get("task_id", ""),
                category=data.get("category", ""),
                prompt=data.get("prompt", ""),
                reference=data.get("reference", ""),
                output=data.get("output", ""),
                status=data.get("status", "pending"),
            ))
    return meta, entries


def apply_review(meta: dict[str, Any], entries: list[ReviewEntry]) -> dict[str, Any]:
    """Re-score the report from human judgments.

    - status "pass": the human overrides the checker - counts as passed
    - status "skip": removed from the totals
    - status "fail": stays failed
    """
    original_total = int(meta.get("total_tasks", 0))
    original_passed = int(meta.get("passed", 0))

    passed = original_passed
    skipped = 0
    judgments: list[dict[str, Any]] = []

    for entry in entries:
        if entry.status == "pass":
            passed += 1
        elif entry.status == "skip":
            skipped += 1
        judgments.append({
            "task_id": entry.task_id,
            "status": entry.status,
            "category": entry.category,
        })

    total = max(0, original_total - skipped)
    accuracy = passed / total if total else 0.0

    return {
        "schema_version": 3,
        "provider": meta.get("provider", "unknown"),
        "model": meta.get("model", ""),
        "suite": meta.get("suite", ""),
        "total_tasks": total,
        "passed": passed,
        "failed": total - passed,
        "skipped": skipped,
        "accuracy": round(accuracy, 4),
        "reviewed": True,
        "judgments": judgments,
    }


def interactive_review(path: Path, yes: bool = False) -> int:
    """Prompt the user for each pending task. Returns the count updated."""
    meta, entries = load_review_queue(path)
    updated = 0

    for entry in entries:
        if entry.status != "pending":
            continue
        if not yes:
            print(f"\n[{entry.task_id}] ({entry.category})")
            print(f"  model output: {entry.output[:200]!r}")
        answer = "pass" if yes else input("judge (p)ass / (f)ail / (s)kip? [p] ").strip().lower()
        if answer in ("f", "fail"):
            entry.status = "fail"
        elif answer in ("s", "skip"):
            entry.status = "skip"
        else:
            entry.status = "pass"
        updated += 1

    lines = [json.dumps({"meta": meta})]
    for entry in entries:
        lines.append(json.dumps({
            "task_id": entry.task_id,
            "category": entry.category,
            "prompt": entry.prompt,
            "reference": entry.reference,
            "output": entry.output,
            "status": entry.status,
        }))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return updated


__all__ = ["ReviewEntry", "write_review_queue", "load_review_queue", "apply_review", "interactive_review"]
