"""AgentEval arena - regression detection.

Compares the baseline repository (base commit) against the agent-modified
workspace to find tests fixed, new failures introduced, and build/lint
regressions. A solution that fixes one test but breaks others is penalized.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .verifiers import VerificationResult

# Best-effort parsers for common test runners. These are heuristics, not
# guarantees: the raw command exit codes always remain the source of truth.
_PYTEST_PASSED = re.compile(r"(\d+) passed")
_PYTEST_FAILED = re.compile(r"(\d+) failed(?:,| in|$)")
_CARGO_COUNT = re.compile(r"test result: (\w+)\. (\d+) passed; (\d+) failed")
_GO_COUNT = re.compile(r"^(?:ok|FAIL)\s+\S+\s+.*?(?:\((\d+\.\d+s)\))?", re.MULTILINE)


@dataclass
class RegressionReport:
    """Baseline vs modified comparison."""

    baseline_passed: int = 0
    baseline_failed: int = 0
    modified_passed: int = 0
    modified_failed: int = 0
    tests_fixed: int = 0
    new_failures: int = 0
    build_regressed: bool = False
    lint_regressed: bool = False
    typecheck_regressed: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def regressions(self) -> int:
        return self.new_failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_passed": self.baseline_passed,
            "baseline_failed": self.baseline_failed,
            "modified_passed": self.modified_passed,
            "modified_failed": self.modified_failed,
            "tests_fixed": self.tests_fixed,
            "new_failures": self.new_failures,
            "build_regressed": self.build_regressed,
            "lint_regressed": self.lint_regressed,
            "typecheck_regressed": self.typecheck_regressed,
            "notes": list(self.notes),
        }


def parse_test_summary(text: str) -> tuple[int, int]:
    """Best-effort (passed, failed) from common test-runner output."""
    m = _CARGO_COUNT.search(text)
    if m:
        return int(m.group(2)), int(m.group(3))
    passed = _PYTEST_PASSED.search(text)
    failed = _PYTEST_FAILED.search(text)
    if passed or failed:
        return (
            int(passed.group(1)) if passed else 0,
            int(failed.group(1)) if failed else 0,
        )
    if "FAIL" in text and "ok" in text:
        # Go: count ok/FAIL lines is complex; fall through to exit-code logic
        pass
    return 0, 0


def _summary_or_truth(result: VerificationResult) -> tuple[int, int]:
    """Use parsed counts when available, else the command-level pass/fail."""
    passed = 0
    failed = 0
    for cmd in result.commands:
        p, f = parse_test_summary(f"{cmd.stdout}\n{cmd.stderr}")
        passed += p
        failed += f
    if passed == 0 and failed == 0:
        passed = result.passed_commands
        failed = result.total_commands - result.passed_commands
    return passed, failed


def compare(
    baseline_tests: VerificationResult | None,
    modified_tests: VerificationResult,
    baseline_build: VerificationResult | None = None,
    modified_build: VerificationResult | None = None,
    baseline_lint: VerificationResult | None = None,
    modified_lint: VerificationResult | None = None,
    baseline_typecheck: VerificationResult | None = None,
    modified_typecheck: VerificationResult | None = None,
) -> RegressionReport:
    """Compare a modified workspace against the baseline."""
    report = RegressionReport()

    if baseline_tests is not None:
        report.baseline_passed, report.baseline_failed = _summary_or_truth(baseline_tests)
        if report.baseline_passed == 0 and report.baseline_failed == 0 and baseline_tests.passed:
            # Baseline fully green (no parseable numbers) - treat as all passed
            report.baseline_passed = baseline_tests.total_commands
            report.baseline_failed = 0

    report.modified_passed, report.modified_failed = _summary_or_truth(modified_tests)

    report.tests_fixed = max(0, report.baseline_failed - report.modified_failed)
    report.new_failures = max(0, report.modified_failed - report.baseline_failed)

    if report.new_failures:
        report.notes.append(f"{report.new_failures} new test failure(s) introduced")

    def _regressed(baseline: VerificationResult | None, modified: VerificationResult) -> bool:
        if baseline is None or baseline.error:
            return False
        return baseline.passed and not modified.passed

    report.build_regressed = _regressed(baseline_build, modified_build)
    report.lint_regressed = _regressed(baseline_lint, modified_lint)
    report.typecheck_regressed = _regressed(baseline_typecheck, modified_typecheck)

    if report.build_regressed:
        report.notes.append("build was passing at baseline but fails after the change")
    if report.lint_regressed:
        report.notes.append("lint was passing at baseline but fails after the change")
    if report.typecheck_regressed:
        report.notes.append("typecheck was passing at baseline but fails after the change")

    return report


__all__ = ["RegressionReport", "compare", "parse_test_summary"]
