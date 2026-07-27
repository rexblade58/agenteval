"""AgentEval - core evaluation engine.

Runs a task suite against a provider and produces a scored report:
accuracy, per-category breakdown, latency, cost, and pass@k.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .providers import BaseProvider, Message
from .tasks import Task, get_tasks, semantic_check

SYSTEM_PROMPT = (
    "You are being evaluated on accuracy and quality. "
    "Answer the user's request directly and concisely. "
    "If asked to write code, output only the code."
)


@dataclass
class TaskResult:
    """The outcome of running one task."""

    task_id: str
    category: str
    passed: bool
    latency_ms: float
    output: str = ""
    prompt: str = ""
    reference: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    attempts: int = 1
    error: str | None = None


@dataclass
class EvaluationReport:
    """Aggregated results across a suite."""

    provider: str
    model: str
    suite: str
    total_tasks: int
    passed: int
    accuracy: float
    avg_latency_ms: float
    total_cost_usd: float
    pass_at_1: float = 0.0
    pass_at_k: float = 0.0
    robustness: float | None = None
    trace_metrics: dict[str, Any] | None = None
    results: list[TaskResult] = field(default_factory=list)
    category_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> int:
        return self.total_tasks - self.passed


class Evaluator:
    """Runs tasks against a provider and scores the results."""

    def __init__(
        self,
        provider: BaseProvider,
        suite: str = "all",
        n_samples: int = 1,
        temperature: float = 0.7,
        scoring: str = "contains",
    ):
        self.provider = provider
        self.suite = suite
        self.n_samples = n_samples  # pass@k support
        self.temperature = temperature
        self.scoring = scoring  # "contains" | "semantic"

    def _check(self, task: Task, output: str) -> bool:
        if self.scoring == "semantic" and task.reference:
            return semantic_check(output, task.reference)
        return task.check(output)

    def run_task(self, task: Task) -> TaskResult:
        """Run a single task (with n_samples attempts for pass@k)."""
        messages = [Message(role="system", content=SYSTEM_PROMPT), Message(role="user", content=task.prompt)]
        results: list[TaskResult] = []

        for _ in range(self.n_samples):
            start = time.perf_counter()
            try:
                resp = self.provider.complete(messages, temperature=self.temperature)
                elapsed = (time.perf_counter() - start) * 1000
                results.append(
                    TaskResult(
                        task_id=task.id,
                        category=task.category,
                        passed=self._check(task, resp.text),
                        latency_ms=elapsed,
                        output=resp.text,
                        prompt=task.prompt,
                        reference=task.reference,
                        input_tokens=resp.input_tokens,
                        output_tokens=resp.output_tokens,
                        cost_usd=resp.cost_usd,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - provider errors are expected
                elapsed = (time.perf_counter() - start) * 1000
                results.append(
                    TaskResult(
                        task_id=task.id,
                        category=task.category,
                        passed=False,
                        latency_ms=elapsed,
                        error=str(exc),
                    )
                )

        # pass@k: passed if ANY of the n samples passed
        best = max(results, key=lambda r: (r.passed, -r.latency_ms))
        best.passed = any(r.passed for r in results)
        best.attempts = self.n_samples
        # Keep the first successful output for reporting
        first_ok = next((r.output for r in results if r.passed), best.output)
        best.output = first_ok
        return best

    def run_suite(self, suite_name: str | None = None) -> EvaluationReport:
        """Run every task in the suite and aggregate results."""
        tasks = get_tasks(suite_name or self.suite)
        results = [self.run_task(t) for t in tasks]

        passed = sum(1 for r in results if r.passed)
        total = len(results)
        accuracy = passed / total if total else 0.0
        avg_latency = sum(r.latency_ms for r in results) / total if total else 0.0
        cost = sum(r.cost_usd for r in results)

        # Category breakdown
        categories: dict[str, dict[str, float]] = {}
        for r in results:
            entry = categories.setdefault(
                r.category,
                {"total": 0.0, "passed": 0.0, "accuracy": 0.0, "avg_latency_ms": 0.0},
            )
            entry["total"] += 1
            if r.passed:
                entry["passed"] += 1
        for entry in categories.values():
            entry["accuracy"] = entry["passed"] / entry["total"] if entry["total"] else 0.0

        # Robustness = accuracy on adversarial tasks (None when not run)
        adv = categories.get("adversarial")
        robustness = adv["accuracy"] if adv else None

        return EvaluationReport(
            provider=self.provider.name,
            model=self.provider.model,
            suite=suite_name or self.suite,
            total_tasks=total,
            passed=passed,
            accuracy=accuracy,
            avg_latency_ms=avg_latency,
            total_cost_usd=cost,
            pass_at_1=accuracy,
            pass_at_k=accuracy,
            robustness=robustness,
            results=results,
            category_breakdown=categories,
            raw={
                "system_prompt": SYSTEM_PROMPT,
                "n_samples": self.n_samples,
                "temperature": self.temperature,
                "scoring": self.scoring,
            },
        )


__all__ = ["Evaluator", "TaskResult", "EvaluationReport"]
