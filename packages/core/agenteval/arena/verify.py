"""AgentEval arena - quick verify command.

Runs the project's tests/build/lint/typecheck in place and reports a
summary, optionally writing an SVG badge for READMEs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .project import ProjectProfile, detect
from .verifiers import BuildVerifier, LintVerifier, TestVerifier, TypecheckVerifier, VerificationResult


def verify_project(workspace: Path, profile: ProjectProfile | None = None,
                   timeout_s: int = 900) -> list[VerificationResult]:
    """Run the standard verifiers against a repository. Returns results."""
    profile = profile or detect(workspace)
    results: list[VerificationResult] = []

    verifiers: list[tuple[str, Any]] = [
        ("tests", TestVerifier(timeout_s=timeout_s)),
        ("build", BuildVerifier(timeout_s=timeout_s)),
        ("lint", LintVerifier(timeout_s=timeout_s)),
        ("typecheck", TypecheckVerifier(timeout_s=timeout_s)),
    ]
    for name, verifier in verifiers:
        results.append(verifier.verify(workspace, profile))
    return results


def summary(results: list[VerificationResult]) -> str:
    """Human-readable verification summary."""
    lines = ["Verification results:\n"]
    all_passed = True
    for result in results:
        if result.total_commands == 0:
            lines.append(f"  {result.name:<10} skipped  ({result.error or 'not configured'})")
            continue
        status = "PASS" if result.passed else "FAIL"
        all_passed = all_passed and result.passed
        lines.append(
            f"  {result.name:<10} {status}  ({result.passed_commands}/{result.total_commands} command(s))"
        )
        if not result.passed and result.error:
            lines.append(f"               {result.error[:160]}")
    lines.append("")
    lines.append("All checks passed." if all_passed else "Some checks failed.")
    return "\n".join(lines)


def all_passed(results: list[VerificationResult]) -> bool:
    return bool(results) and all(r.passed for r in results)


__all__ = ["verify_project", "summary", "all_passed"]
