"""AgentEval arena - environment readiness check (agenteval doctor).

Checks tooling without ever displaying secrets or credentials.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _version(name: str) -> str:
    try:
        out = subprocess.run([name, "--version"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else out.stderr.strip().splitlines()[0]
    except (OSError, subprocess.SubprocessError):
        return ""


def run_doctor() -> list[Check]:
    """Run all environment checks. Returns a list of results."""
    checks: list[Check] = []

    checks.append(Check("git", _which("git"), _version("git")))

    docker = _which("docker")
    checks.append(Check("docker", docker, "optional - worktrees are used by default" if not docker else _version("docker")))

    python = _which("python")
    checks.append(Check("python", python, _version("python") if python else ""))

    node = _which("node")
    checks.append(Check("node", node, _version("node") if node else "optional for JS/TS projects"))

    npm = _which("npm")
    if not node and npm:
        checks.append(Check("npm", True, _version("npm")))
    elif node:
        checks.append(Check("npm", npm, _version("npm") if npm else ""))

    agent_checks: list[tuple[str, str]] = [
        ("codex", "Codex CLI"),
        ("claude", "Claude Code"),
        ("gemini", "Gemini CLI"),
        ("opencode", "OpenCode"),
        ("aider", "Aider"),
    ]
    for binary, label in agent_checks:
        checks.append(Check(label, _which(binary), _version(binary) if _which(binary) else "not installed"))

    playwright = _which("npx") and _npx_playwright()
    checks.append(Check("Playwright", playwright, "optional - browser verification (Phase 3)" if not playwright else "available"))

    return checks


def critical_ok(checks: list[Check]) -> bool:
    """Whether the essentials (git + python) are available for arena runs."""
    names = {c.name for c in checks if not c.ok}
    return not (names & {"git", "python"})


def _npx_playwright() -> bool:
    try:
        out = subprocess.run(
            ["npx", "--no-install", "playwright", "--version"],
            capture_output=True, text=True, timeout=15,
        )
        return out.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


__all__ = ["Check", "run_doctor"]
