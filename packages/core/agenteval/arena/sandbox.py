"""AgentEval arena - Docker sandbox isolation.

Runs agent commands and verification inside a container with:
- the workspace mounted read-write (the only host path visible)
- configurable network isolation (--network none)
- resource limits (CPU, memory, pids)

Worktree execution remains the default; Docker is opt-in via
--sandbox docker. Treat shell-running agents as untrusted either way.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exec import ExecResult, run_command

DEFAULT_IMAGE = "python:3.11-slim"
DEFAULT_CONTAINER_WORKDIR = "/workspace"


@dataclass
class SandboxConfig:
    """Docker sandbox settings (sandbox: section of agenteval.yaml)."""

    image: str = DEFAULT_IMAGE
    network: str = "bridge"  # "bridge" | "none"
    cpus: str | None = None       # e.g. "2"
    memory: str | None = None     # e.g. "2g"
    pids_limit: int | None = None  # e.g. 256
    label_prefix: str = "agenteval"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SandboxConfig":
        if not data:
            return cls()
        return cls(
            image=str(data.get("image", DEFAULT_IMAGE)),
            network=str(data.get("network", "bridge")),
            cpus=str(data["cpus"]) if data.get("cpus") else None,
            memory=str(data["memory"]) if data.get("memory") else None,
            pids_limit=int(data["pids_limit"]) if data.get("pids_limit") else None,
            label_prefix=str(data.get("label_prefix", "agenteval")),
        )


class DockerSandbox:
    """Wraps commands so they execute inside a Docker container."""

    def __init__(self, config: SandboxConfig | None = None):
        self.config = config or SandboxConfig()

    @staticmethod
    def available() -> bool:
        """Whether docker is installed and the daemon responds."""
        if shutil.which("docker") is None:
            return False
        try:
            result = subprocess.run(
                ["docker", "info"], capture_output=True, timeout=15
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _common_args(self, workspace: Path, name: str) -> list[str]:
        args = [
            "docker", "run", "--rm",
            "--name", name,
            "--label", f"{self.config.label_prefix}=arena",
            "--workdir", DEFAULT_CONTAINER_WORKDIR,
            "--volume", f"{workspace.resolve()}:{DEFAULT_CONTAINER_WORKDIR}",
        ]
        if self.config.network:
            args += ["--network", self.config.network]
        if self.config.cpus:
            args += ["--cpus", self.config.cpus]
        if self.config.memory:
            args += ["--memory", self.config.memory]
        if self.config.pids_limit:
            args += ["--pids-limit", str(self.config.pids_limit)]
        return args

    def wrap_command(self, command: list[str], workspace: Path, name: str) -> list[str]:
        """Wrap an argv-style command (agent adapters, shell=False)."""
        return self._common_args(workspace, name) + [self.config.image] + command

    def wrap_shell(self, command: str, workspace: Path, name: str) -> list[str]:
        """Wrap a shell string (verifiers, shell=True) via sh -c inside the image."""
        return self._common_args(workspace, name) + [
            self.config.image, "sh", "-c", command,
        ]

    def run(
        self,
        command: list[str],
        workspace: Path,
        timeout_s: float,
        env: dict[str, str] | None = None,
        shell: bool = False,
        name: str = "agenteval",
    ) -> ExecResult:
        """Execute a command inside the sandbox with a hard timeout."""
        if shell:
            wrapped = self.wrap_shell(command[0], workspace, name)
        else:
            wrapped = self.wrap_command(command, workspace, name)
        result = run_command(wrapped, workspace, timeout_s, env=env)
        return result


__all__ = ["SandboxConfig", "DockerSandbox", "DEFAULT_IMAGE"]
