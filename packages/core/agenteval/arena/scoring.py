"""AgentEval arena - transparent scoring.

Scores are computed from objective, executable evidence with configurable
weights. Functional correctness (real tests passing) dominates. An LLM
judge can never override hard test failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .agents import AgentStatus
from .regression import RegressionReport
from .verifiers import VerificationResult

DEFAULT_WEIGHTS: dict[str, float] = {
    "functional": 0.50,   # real tests passing (agent's own suite result)
    "regression": 0.20,   # no new failures vs baseline
    "build": 0.10,        # build/check passes
    "quality": 0.10,      # lint + typecheck
    "cost": 0.05,         # cheaper is better (relative to the arena max)
    "speed": 0.05,        # faster is better (relative to the arena max)
}

STATE_SCORE: dict[AgentStatus, float] = {
    AgentStatus.PASS: 1.0,
    AgentStatus.PARTIAL: 0.6,
    AgentStatus.FAIL: 0.0,
    AgentStatus.TIMEOUT: 0.0,
    AgentStatus.AGENT_ERROR: 0.0,
    AgentStatus.ENVIRONMENT_ERROR: 0.0,
    AgentStatus.VERIFICATION_ERROR: 0.0,
    AgentStatus.CANCELLED: 0.0,
}


@dataclass
class DimensionScore:
    """One scored dimension with its evidence."""

    name: str
    weight: float
    score: float  # 0..1
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "score": round(self.score, 4),
            "detail": self.detail,
        }


@dataclass
class ArenaScore:
    """Overall score for one agent attempt."""

    total: float  # 0..100
    state: AgentStatus
    dimensions: list[DimensionScore] = field(default_factory=list)
    disqualification: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": round(self.total, 1),
            "state": self.state.value,
            "disqualification": self.disqualification,
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def _tests_score(tests: VerificationResult | None) -> DimensionScore:
    if tests is None:
        return DimensionScore("functional", DEFAULT_WEIGHTS["functional"], 0.0, "no test run")
    if not tests.total_commands:
        # No tests configured for this project - neutral, not a failure
        return DimensionScore(
            "functional",
            DEFAULT_WEIGHTS["functional"],
            1.0,
            tests.error or "no tests configured",
        )
    score = tests.passed_commands / tests.total_commands
    return DimensionScore(
        "functional",
        DEFAULT_WEIGHTS["functional"],
        score,
        f"{tests.passed_commands}/{tests.total_commands} command(s) passed",
    )


def _regression_score(regression: RegressionReport | None) -> DimensionScore:
    weight = DEFAULT_WEIGHTS["regression"]
    if regression is None:
        return DimensionScore("regression", weight, 1.0, "no baseline available")
    regressions = regression.new_failures
    if regressions <= 0:
        return DimensionScore("regression", weight, 1.0, "no new failures")
    penalty = min(1.0, regressions / 5.0)
    if regression.build_regressed or regression.lint_regressed or regression.typecheck_regressed:
        penalty = min(1.0, penalty + 0.25)
    return DimensionScore(
        "regression",
        weight,
        round(1.0 - penalty, 4),
        f"{regressions} new failure(s); "
        f"build_regressed={regression.build_regressed}, "
        f"lint_regressed={regression.lint_regressed}, "
        f"typecheck_regressed={regression.typecheck_regressed}",
    )


def _build_score(build: VerificationResult | None) -> DimensionScore:
    weight = DEFAULT_WEIGHTS["build"]
    if build is None or build.error:
        return DimensionScore("build", weight, 1.0, "no build configured")
    if not build.total_commands:
        return DimensionScore("build", weight, 1.0, "no build configured")
    score = build.passed_commands / build.total_commands
    return DimensionScore("build", weight, score, f"{build.passed_commands}/{build.total_commands} passed")


def _quality_score(lint: VerificationResult | None, typecheck: VerificationResult | None) -> DimensionScore:
    weight = DEFAULT_WEIGHTS["quality"]
    parts: list[tuple[float, str]] = []
    for name, result in (("lint", lint), ("typecheck", typecheck)):
        if result is None or result.error or not result.total_commands:
            parts.append((1.0, f"{name}: not configured"))
        else:
            parts.append((result.passed_commands / result.total_commands, f"{name}: {result.passed_commands}/{result.total_commands}"))
    score = sum(p for p, _ in parts) / len(parts) if parts else 1.0
    return DimensionScore("quality", weight, round(score, 4), "; ".join(d for _, d in parts))


def _cost_score(cost_usd: float, max_cost: float) -> DimensionScore:
    weight = DEFAULT_WEIGHTS["cost"]
    if max_cost <= 0 or cost_usd <= 0:
        return DimensionScore("cost", weight, 1.0, "no cost data")
    score = min(1.0, max_cost / cost_usd) if cost_usd > 0 else 1.0
    return DimensionScore("cost", weight, round(score, 4), f"${cost_usd:.4f} vs arena max ${max_cost:.4f}")


def _speed_score(duration_s: float, min_duration: float) -> DimensionScore:
    weight = DEFAULT_WEIGHTS["speed"]
    if min_duration <= 0 or duration_s <= 0:
        return DimensionScore("speed", weight, 1.0, "no timing data")
    score = min(1.0, min_duration / duration_s)
    return DimensionScore("speed", weight, round(score, 4), f"{duration_s:.0f}s vs fastest {min_duration:.0f}s")


def score_attempt(
    state: AgentStatus,
    tests: VerificationResult | None,
    regression: RegressionReport | None,
    build: VerificationResult | None = None,
    lint: VerificationResult | None = None,
    typecheck: VerificationResult | None = None,
    browser: VerificationResult | None = None,
    cost_usd: float = 0.0,
    duration_s: float = 0.0,
    max_cost: float = 0.0,
    min_duration: float = 0.0,
    weights: dict[str, float] | None = None,
) -> ArenaScore:
    """Compute the transparent score for one agent attempt."""
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    if state in (AgentStatus.TIMEOUT, AgentStatus.AGENT_ERROR, AgentStatus.ENVIRONMENT_ERROR,
                 AgentStatus.CANCELLED):
        return ArenaScore(
            total=0.0,
            state=state,
            dimensions=[],
            disqualification=f"agent ended with {state.value}",
        )

    dimensions = [
        _tests_score(tests),
        _regression_score(regression),
        _build_score(build),
        _quality_score(lint, typecheck),
        _cost_score(cost_usd, max_cost),
        _speed_score(duration_s, min_duration),
    ]
    for dim in dimensions:
        dim.weight = w.get(dim.name, dim.weight)

    # Hard gates: tests and (when configured) browser verification must pass.
    # An LLM judge cannot override these.
    tests_dim = next(d for d in dimensions if d.name == "functional")
    browser_failed = browser is not None and not browser.passed and browser.total_commands > 0
    if tests_dim.score == 0.0 and tests is not None and tests.total_commands > 0:
        total = 0.0
        disqual = "hard tests failed"
    elif browser_failed:
        total = round(sum(d.weight * d.score for d in dimensions) * 100 * 0.5, 1)
        disqual = f"browser verification failed: {browser.error}"
    else:
        total = sum(d.weight * d.score for d in dimensions) * 100
        disqual = None

    final_state = state
    if disqual is None and total < 60:
        final_state = AgentStatus.PARTIAL if total > 0 else AgentStatus.FAIL
    elif disqual is None and total >= 60:
        final_state = AgentStatus.PASS

    return ArenaScore(total=round(total, 1), state=final_state, dimensions=dimensions, disqualification=disqual)


__all__ = ["DEFAULT_WEIGHTS", "ArenaScore", "DimensionScore", "score_attempt"]
