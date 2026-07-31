"""AgentEval arena - objective verification engine.

Verifiers execute real commands (tests, build, lint, typecheck) against a
workspace and record structured results. Community verifiers implement the
Verifier interface; nothing else needs to change.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exec import ExecResult, run_command
from .project import ProjectProfile


@dataclass
class VerificationResult:
    """Structured outcome of one verifier."""

    name: str
    passed: bool
    passed_commands: int = 0
    total_commands: int = 0
    commands: list[ExecResult] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "passed": self.passed,
            "passed_commands": self.passed_commands,
            "total_commands": self.total_commands,
            "error": self.error,
            "commands": [
                {
                    "command": c.command,
                    "exit_code": c.exit_code,
                    "duration_s": round(c.duration_s, 3),
                    "timed_out": c.timed_out,
                    "passed": c.ok,
                    "stdout": c.stdout[:2000],
                    "stderr": c.stderr[:2000],
                }
                for c in self.commands
            ],
        }


class Verifier(ABC):
    """Interface every verifier implements."""

    name: str = "base"

    @abstractmethod
    def verify(self, workspace: Path, profile: ProjectProfile) -> VerificationResult:
        """Run verification commands and return structured results."""


class CommandVerifier(Verifier):
    """Runs an explicit list of commands (from config or acceptance criteria)."""

    name = "command"

    def __init__(self, commands: list[str], name: str | None = None, timeout_s: int = 600):
        self.commands = commands
        self._name = name
        self.timeout_s = timeout_s

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name or "command"

    def verify(self, workspace: Path, profile: ProjectProfile | None = None) -> VerificationResult:
        results = [
            run_command([cmd], workspace, self.timeout_s, shell=True)
            for cmd in self.commands
        ]
        passed = sum(1 for r in results if r.ok)
        return VerificationResult(
            name=self.name,
            passed=passed == len(results) and bool(results),
            passed_commands=passed,
            total_commands=len(results),
            commands=results,
        )


def _run_commands(workspace: Path, commands: list[str], timeout_s: int) -> list[ExecResult]:
    results = []
    for cmd in commands:
        # Allow shell syntax (&&, env vars) only for explicit config commands;
        # detected defaults are simple single commands.
        results.append(run_command([cmd], workspace, timeout_s, shell=True))
    return results


class TestVerifier(CommandVerifier):
    """Runs the project's test commands."""

    name = "tests"

    def __init__(self, commands: list[str] | None = None, timeout_s: int = 900):
        super().__init__(commands or [], name="tests", timeout_s=timeout_s)

    def verify(self, workspace: Path, profile: ProjectProfile) -> VerificationResult:
        commands = self.commands or profile.test or []
        if not commands:
            return VerificationResult(name=self.name, passed=True, error="no test commands configured or detected")
        results = _run_commands(workspace, commands, self.timeout_s)
        passed = sum(1 for r in results if r.ok)
        return VerificationResult(
            name=self.name,
            passed=passed == len(results) and bool(results),
            passed_commands=passed,
            total_commands=len(results),
            commands=results,
        )


class BuildVerifier(CommandVerifier):
    """Runs the project's build commands."""

    name = "build"

    def __init__(self, commands: list[str] | None = None, timeout_s: int = 900):
        super().__init__(commands or [], name="build", timeout_s=timeout_s)

    def verify(self, workspace: Path, profile: ProjectProfile) -> VerificationResult:
        commands = self.commands or profile.build or []
        if not commands:
            return VerificationResult(name=self.name, passed=True, error="no build commands configured or detected")
        results = _run_commands(workspace, commands, self.timeout_s)
        passed = sum(1 for r in results if r.ok)
        return VerificationResult(
            name=self.name,
            passed=passed == len(results) and bool(results),
            passed_commands=passed,
            total_commands=len(results),
            commands=results,
        )


class LintVerifier(CommandVerifier):
    """Runs the project's lint commands."""

    name = "lint"

    def __init__(self, commands: list[str] | None = None, timeout_s: int = 600):
        super().__init__(commands or [], name="lint", timeout_s=timeout_s)

    def verify(self, workspace: Path, profile: ProjectProfile) -> VerificationResult:
        commands = self.commands or profile.lint or []
        if not commands:
            return VerificationResult(name=self.name, passed=True, error="no lint commands configured or detected")
        results = _run_commands(workspace, commands, self.timeout_s)
        passed = sum(1 for r in results if r.ok)
        return VerificationResult(
            name=self.name,
            passed=passed == len(results) and bool(results),
            passed_commands=passed,
            total_commands=len(results),
            commands=results,
        )


class TypecheckVerifier(CommandVerifier):
    """Runs the project's typecheck commands."""

    name = "typecheck"

    def __init__(self, commands: list[str] | None = None, timeout_s: int = 600):
        super().__init__(commands or [], name="typecheck", timeout_s=timeout_s)

    def verify(self, workspace: Path, profile: ProjectProfile) -> VerificationResult:
        commands = self.commands or profile.typecheck or []
        if not commands:
            return VerificationResult(name=self.name, passed=True, error="no typecheck commands configured or detected")
        results = _run_commands(workspace, commands, self.timeout_s)
        passed = sum(1 for r in results if r.ok)
        return VerificationResult(
            name=self.name,
            passed=passed == len(results) and bool(results),
            passed_commands=passed,
            total_commands=len(results),
            commands=results,
        )


def _lazy_browser_verifier(**kwargs: Any) -> Verifier:
    """Import BrowserVerifier lazily so Playwright is never a hard dependency."""
    from .browser import BrowserConfig, BrowserVerifier

    config = kwargs.get("config")
    if config is None and "browser_config" in kwargs:
        config = kwargs["browser_config"]
    if isinstance(config, dict):
        config = BrowserConfig.from_dict(config)
    return BrowserVerifier(config=config)


VERIFIER_REGISTRY: dict[str, type[Verifier]] = {
    "tests": TestVerifier,
    "build": BuildVerifier,
    "lint": LintVerifier,
    "typecheck": TypecheckVerifier,
    "browser": _lazy_browser_verifier,
}


def create_verifier(name: str, **kwargs: Any) -> Verifier:
    if name not in VERIFIER_REGISTRY:
        raise ValueError(f"unknown verifier '{name}'. Available: {', '.join(sorted(VERIFIER_REGISTRY))}")
    return VERIFIER_REGISTRY[name](**kwargs)


def list_verifiers() -> list[dict[str, str]]:
    entries = []
    for name in sorted(VERIFIER_REGISTRY):
        if name == "browser":
            entries.append({"name": name, "verifier": "BrowserVerifier (playwright)"})
        else:
            entries.append({"name": name, "verifier": VERIFIER_REGISTRY[name].__name__})
    return entries


__all__ = [
    "VerificationResult",
    "Verifier",
    "CommandVerifier",
    "TestVerifier",
    "BuildVerifier",
    "LintVerifier",
    "TypecheckVerifier",
    "VERIFIER_REGISTRY",
    "create_verifier",
    "list_verifiers",
]
