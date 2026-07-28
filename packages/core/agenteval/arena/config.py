"""AgentEval arena - configuration.

Loads agenteval.yaml from the repository root and merges it with CLI
arguments. Explicit configuration overrides auto-detection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

from .arena import ArenaConfig
from .project import ProjectProfile


def load_agent_configs(repo: Path) -> dict[str, dict[str, Any]]:
    """Load custom agent definitions from agenteval.yaml (agents: section)."""
    data = _load_file(repo)
    agents = data.get("agents", {}) if data else {}
    if isinstance(agents, dict):
        return {name: cfg for name, cfg in agents.items() if isinstance(cfg, dict)}
    return {}


def load_verify_commands(repo: Path) -> dict[str, list[str]]:
    data = _load_file(repo)
    verification = data.get("verification", {}) if data else {}
    verify = verification.get("verify", {}) if isinstance(verification, dict) else {}
    if isinstance(verify, dict):
        return {name: list(cmds) for name, cmds in verify.items() if isinstance(cmds, list)}
    return {}


def load_weights(repo: Path) -> dict[str, float]:
    data = _load_file(repo)
    scoring = data.get("scoring", {}) if data else {}
    if not isinstance(scoring, dict):
        return {}
    return {k: float(v) for k, v in scoring.items() if isinstance(v, (int, float))}


def load_profile_override(repo: Path) -> ProjectProfile | None:
    """Load a project: section as an explicit profile, or None."""
    data = _load_file(repo)
    project = data.get("project", {}) if data else {}
    if not isinstance(project, dict) or not project:
        return None
    profile = ProjectProfile(
        language=str(project.get("language", "unknown")),
        package_manager=project.get("package_manager"),
        install=_as_list(project.get("install")),
        test=_as_list(project.get("test")),
        build=_as_list(project.get("build")),
        lint=_as_list(project.get("lint")),
        typecheck=_as_list(project.get("typecheck")),
        detected_by="agenteval.yaml",
    )
    return profile


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _load_file(repo: Path) -> dict[str, Any]:
    if yaml is None:  # pragma: no cover
        return {}
    for name in ("agenteval.yaml", "agenteval.yml", ".agenteval.yaml"):
        path = repo / name
        if path.is_file():
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
            except yaml.YAMLError as exc:
                print(f"warning: ignoring invalid {name}: {exc}")
    return {}


def config_from_repo(repo: Path, cli: dict[str, Any]) -> ArenaConfig:
    """Build an ArenaConfig from agenteval.yaml + CLI overrides."""
    data = _load_file(repo)
    arena = data.get("arena", {}) if data else {}
    if not isinstance(arena, dict):
        arena = {}

    agents: list[str] = list(cli.get("agents") or [])
    if not agents and isinstance(arena.get("agents"), list):
        agents = [str(a) for a in arena["agents"]]
    if not agents:
        agents = ["command"]

    timeout = cli.get("timeout_s") or int(arena.get("timeout", 900))
    parallel = cli.get("parallel")
    if parallel is None:
        parallel = bool(arena.get("parallel", False))

    verifiers = cli.get("verifiers")
    if not verifiers and isinstance(arena.get("verifiers"), list):
        verifiers = [str(v) for v in arena["verifiers"]]

    return ArenaConfig(
        repo=cli.get("repo") or ".",
        task=cli.get("task") or "",
        task_file=cli.get("task_file"),
        agents=agents,
        timeout_s=int(timeout),
        parallel=parallel,
        commit=cli.get("commit"),
        verifiers=verifiers or ["tests", "build", "lint", "typecheck"],
        runs=int(cli.get("runs") or 1),
        keep_worktrees=bool(cli.get("keep_worktrees")),
    )


__all__ = [
    "load_agent_configs",
    "load_verify_commands",
    "load_weights",
    "load_profile_override",
    "config_from_repo",
]
