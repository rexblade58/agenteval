"""AgentEval arena - autonomous coding agent adapters.

An AgentAdapter is a program that can modify a repository to accomplish a
task. This is deliberately separate from LLM *providers*: a provider emits
responses; an agent autonomously reads, edits, runs commands, and iterates.

Adapters are pluggable. Built-ins target common CLIs (Codex, Claude Code,
Gemini CLI, OpenCode, Aider) plus a generic command adapter that can wrap
almost any executable.
"""

from __future__ import annotations

import dataclasses
import shlex
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .exec import run_command


class AgentStatus(str, Enum):
    """Explicit outcome states - never flatten failures into a number."""

    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    AGENT_ERROR = "AGENT_ERROR"
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"
    VERIFICATION_ERROR = "VERIFICATION_ERROR"
    CANCELLED = "CANCELLED"


@dataclass
class AgentRunResult:
    """Everything observed about one agent execution."""

    agent: str
    status: AgentStatus = AgentStatus.PASS
    exit_code: int | None = None
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error: str | None = None
    commands_executed: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    diff_stat: str = ""
    git_diff: str = ""
    token_usage: dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentAdapter(ABC):
    """Interface every coding agent integration implements."""

    name: str = "base"
    display_name: str = ""
    description: str = ""
    version: str = "unknown"

    def __init__(self, timeout_s: int = 900):
        self.timeout_s = timeout_s

    @abstractmethod
    def run(self, workspace: Path, task: str, env: dict[str, str] | None = None) -> AgentRunResult:
        """Run the agent against a task inside `workspace`."""

    def available(self) -> bool:
        """Whether the underlying executable appears to be installed."""
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name or self.name,
            "description": self.description,
            "version": self.version,
        }


class CommandAgent(AgentAdapter):
    """Generic adapter: runs an arbitrary command with the task interpolated.

    The command template may contain ``{task}`` (quoted task text) and
    ``{workspace}`` (absolute path to the isolated worktree).
    """

    name = "command"

    def __init__(
        self,
        command: str,
        name: str | None = None,
        timeout_s: int = 900,
        shell: bool = False,
        env: dict[str, str] | None = None,
        description: str = "",
    ):
        super().__init__(timeout_s=timeout_s)
        self.command_template = command
        self._name = name
        self.shell = shell
        self.extra_env = env or {}
        self.description = description

    @property
    def name(self) -> str:  # type: ignore[override]
        return self._name or "command"

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def _build_command(self, workspace: Path, task: str) -> list[str]:
        rendered = (
            self.command_template
            .replace("{task}", shlex.quote(task))
            .replace("{workspace}", str(workspace))
        )
        return [rendered] if self.shell else shlex.split(rendered)

    def run(self, workspace: Path, task: str, env: dict[str, str] | None = None) -> AgentRunResult:
        merged_env = dict(self.extra_env)
        if env:
            merged_env.update(env)

        cmd = self._build_command(workspace, task)
        result = run_command(cmd, workspace, self.timeout_s, env=merged_env, shell=self.shell)

        if result.error and result.exit_code is None:
            status = AgentStatus.AGENT_ERROR
        elif result.timed_out:
            status = AgentStatus.TIMEOUT
        elif result.exit_code == 0:
            status = AgentStatus.PASS
        else:
            status = AgentStatus.FAIL

        return AgentRunResult(
            agent=self.name,
            status=status,
            exit_code=result.exit_code,
            duration_s=result.duration_s,
            stdout=result.stdout,
            stderr=result.stderr,
            error=result.error or (None if result.exit_code == 0 else f"exit code {result.exit_code}"),
            commands_executed=[result.command],
        )


class CodexAgent(CommandAgent):
    """OpenAI Codex CLI (codex exec, non-interactive)."""

    name = "codex"
    display_name = "Codex CLI"
    description = "OpenAI Codex CLI in exec mode"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = (
            f"codex exec --skip-git-repo-check --sandbox workspace-write "
            f"{extra_args} {{task}}"
        ).strip()
        super().__init__(template, name="codex", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("codex") is not None


class ClaudeCodeAgent(CommandAgent):
    """Anthropic Claude Code (claude -p, non-interactive)."""

    name = "claude"
    display_name = "Claude Code"
    description = "Anthropic Claude Code in print mode"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = f"claude -p --dangerously-skip-permissions {extra_args} {{task}}".strip()
        super().__init__(template, name="claude", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("claude") is not None


class GeminiCliAgent(CommandAgent):
    """Google Gemini CLI (gemini -p / gemini coding)."""

    name = "gemini"
    display_name = "Gemini CLI"
    description = "Google Gemini CLI in print mode"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = f"gemini -p {extra_args} {{task}}".strip()
        super().__init__(template, name="gemini", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("gemini") is not None


class OpenCodeAgent(CommandAgent):
    """OpenCode CLI in headless run mode."""

    name = "opencode"
    display_name = "OpenCode"
    description = "OpenCode CLI headless run"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = f"opencode run {extra_args} {{task}}".strip()
        super().__init__(template, name="opencode", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("opencode") is not None


class AiderAgent(CommandAgent):
    """Aider in code-only mode."""

    name = "aider"
    display_name = "Aider"
    description = "Aider (AI pair programming) in code mode"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = f"aider --message {{task}} --yes-always --no-suggest-shell-commands {extra_args}".strip()
        super().__init__(template, name="aider", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("aider") is not None


AGENT_REGISTRY: dict[str, type[AgentAdapter]] = {
    "command": CommandAgent,
    "codex": CodexAgent,
    "claude": ClaudeCodeAgent,
    "gemini": GeminiCliAgent,
    "opencode": OpenCodeAgent,
    "aider": AiderAgent,
}


def create_agent(name: str, timeout_s: int = 900, config: dict[str, Any] | None = None) -> AgentAdapter:
    """Factory: built-in by name, or a CommandAgent from a YAML config dict.

    YAML config example::

        my-agent:
          command: my-agent run "{task}"
          timeout: 900
          shell: true
          description: My custom agent
    """
    if config:
        if "command" not in config:
            raise ValueError(f"agent config '{name}' requires a 'command' key")
        return CommandAgent(
            command=config["command"],
            name=name,
            timeout_s=int(config.get("timeout", timeout_s)),
            shell=bool(config.get("shell", False)),
            env=config.get("env"),
            description=config.get("description", ""),
        )
    if name not in AGENT_REGISTRY:
        raise ValueError(
            f"unknown agent '{name}'. Available: {', '.join(sorted(AGENT_REGISTRY))}"
        )
    return AGENT_REGISTRY[name](timeout_s=timeout_s)


def list_agents() -> list[dict[str, Any]]:
    entries = []
    for name in sorted(AGENT_REGISTRY):
        cls = AGENT_REGISTRY[name]
        try:
            agent = cls() if name != "command" else CommandAgent(command="true", name="command")
        except TypeError:  # pragma: no cover - defensive
            agent = CommandAgent(command="true", name=name)
        entries.append(agent.to_dict())
    return entries


__all__ = [
    "AgentStatus",
    "AgentRunResult",
    "AgentAdapter",
    "CommandAgent",
    "CodexAgent",
    "ClaudeCodeAgent",
    "GeminiCliAgent",
    "OpenCodeAgent",
    "AiderAgent",
    "AGENT_REGISTRY",
    "create_agent",
    "list_agents",
]
