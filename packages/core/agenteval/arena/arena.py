"""AgentEval arena - orchestrator.

Runs multiple coding agents against the same task in isolated git
worktrees, verifies each result with real commands, detects regressions,
scores transparently, and ranks the attempts.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import __version__
from .agents import AgentAdapter, AgentRunResult, AgentStatus
from .project import ProjectProfile, detect
from .regression import RegressionReport, compare
from .results import AgentResult, ArenaResult
from .scoring import score_attempt
from .verifiers import BuildVerifier, LintVerifier, TestVerifier, TypecheckVerifier, VerificationResult
from .workspace import WorktreeManager


@dataclass
class ArenaConfig:
    """Resolved configuration for one arena run."""

    repo: str | Path = "."
    task: str = ""
    task_file: Path | None = None
    agents: list[str] = field(default_factory=list)
    agent_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    runs: int = 1
    parallel: bool = False
    timeout_s: int = 900
    commit: str | None = None
    verifiers: list[str] = field(default_factory=lambda: ["tests", "build", "lint", "typecheck"])
    weights: dict[str, float] = field(default_factory=dict)
    verify_commands: dict[str, list[str]] = field(default_factory=dict)
    profile: ProjectProfile | None = None
    keep_worktrees: bool = False
    max_parallel: int = 4
    quiet: bool = False


class ArenaRunner:
    """Executes an arena run end-to-end."""

    def __init__(self, config: ArenaConfig):
        self.config = config
        self._manager: WorktreeManager | None = None
        self._baseline_tests: VerificationResult | None = None
        self._baseline_build: VerificationResult | None = None
        self._baseline_lint: VerificationResult | None = None
        self._baseline_typecheck: VerificationResult | None = None
        self._profile: ProjectProfile | None = None

    def _log(self, message: str) -> None:
        if not self.config.quiet:
            print(message)

    # ------------------------------------------------------------------ setup
    def _resolve_profile(self) -> ProjectProfile:
        if self.config.profile is not None:
            return self.config.profile
        workspace = self._manager._local_repo  # noqa: SLF001 - the manager owns it
        if workspace is None:
            raise RuntimeError("repository not initialized")
        return detect(workspace)

    def _verifier(self, name: str) -> Any:
        commands = self.config.verify_commands.get(name)
        if name == "tests":
            return TestVerifier(commands, timeout_s=self.config.timeout_s)
        if name == "build":
            return BuildVerifier(commands, timeout_s=self.config.timeout_s)
        if name == "lint":
            return LintVerifier(commands, timeout_s=self.config.timeout_s)
        if name == "typecheck":
            return TypecheckVerifier(commands, timeout_s=self.config.timeout_s)
        raise ValueError(f"unknown verifier '{name}'")

    def _run_baseline(self) -> None:
        """Verify the untouched base commit before any agent runs."""
        if "tests" not in self.config.verifiers:
            return
        self._log("Running baseline verification...")
        baseline_ws = self._manager.create("baseline")
        try:
            tests = self._verifier("tests")
            self._baseline_tests = tests.verify(baseline_ws, self._profile)
            if self._baseline_tests.total_commands:
                self._log(f"  baseline tests: {self._baseline_tests.passed_commands}/"
                          f"{self._baseline_tests.total_commands} passed")
            else:
                self._log("  baseline tests: no test commands found")
            if "build" in self.config.verifiers:
                self._baseline_build = self._verifier("build").verify(baseline_ws, self._profile)
            if "lint" in self.config.verifiers:
                self._baseline_lint = self._verifier("lint").verify(baseline_ws, self._profile)
            if "typecheck" in self.config.verifiers:
                self._baseline_typecheck = self._verifier("typecheck").verify(baseline_ws, self._profile)
        finally:
            self._manager.cleanup(baseline_ws)

    # ------------------------------------------------------------ agent runs
    def _collect_attempt(self, agent: AgentAdapter, run_index: int) -> AgentResult:
        """Run the agent, verify, and capture evidence (no final scoring)."""
        workspace = self._manager.create(f"run-{agent.name}")
        run: AgentRunResult | None = None
        try:
            self._log(f"[{run_index}] running {agent.name} ...")
            started = time.perf_counter()
            run = agent.run(workspace, self.config.task)
            run.duration_s = time.perf_counter() - started

            diff = self._manager.diff(workspace)
            run.files_changed = diff.files_changed
            run.diff_stat = diff.diff_stat
            run.git_diff = diff.git_diff

            tests = build = lint = typecheck = None
            if "tests" in self.config.verifiers:
                tests = self._verifier("tests").verify(workspace, self._profile)
            if "build" in self.config.verifiers:
                build = self._verifier("build").verify(workspace, self._profile)
            if "lint" in self.config.verifiers:
                lint = self._verifier("lint").verify(workspace, self._profile)
            if "typecheck" in self.config.verifiers:
                typecheck = self._verifier("typecheck").verify(workspace, self._profile)

            regression = compare(
                baseline_tests=self._baseline_tests,
                modified_tests=tests,
                baseline_build=self._baseline_build,
                modified_build=build,
                baseline_lint=self._baseline_lint,
                modified_lint=lint,
                baseline_typecheck=self._baseline_typecheck,
                modified_typecheck=typecheck,
            )

            return AgentResult(
                agent=agent.name,
                run_index=run_index,
                status=run.status,
                score=None,  # type: ignore[arg-type] - scored in finalize
                run=run,
                tests=tests,
                build=build,
                lint=lint,
                typecheck=typecheck,
                regression=regression,
            )
        except Exception as exc:  # noqa: BLE001 - arena must never die silently
            if run is None:
                run = AgentRunResult(agent=agent.name, status=AgentStatus.ENVIRONMENT_ERROR, error=str(exc))
            else:
                run.status = AgentStatus.ENVIRONMENT_ERROR
                run.error = f"{run.error or ''}; {exc}".strip("; ")
            return AgentResult(
                agent=agent.name,
                run_index=run_index,
                status=run.status,
                score=None,  # type: ignore[arg-type]
                run=run,
            )
        finally:
            if not self.config.keep_worktrees:
                self._manager.cleanup(workspace)

    @staticmethod
    def _finalize(results: list[AgentResult], weights: dict[str, float]) -> None:
        """Score all attempts with arena-wide normalization pools."""
        durations = [r.run.duration_s for r in results if r.run.duration_s > 0]
        costs = [r.run.cost_usd for r in results if r.run.cost_usd > 0]
        min_duration = min(durations) if durations else 0.0
        max_cost = max(costs) if costs else 0.0

        for result in results:
            result.score = score_attempt(
                state=result.status,
                tests=result.tests,
                regression=result.regression,
                build=result.build,
                lint=result.lint,
                typecheck=result.typecheck,
                cost_usd=result.run.cost_usd,
                duration_s=result.run.duration_s,
                max_cost=max_cost,
                min_duration=min_duration,
                weights=weights,
            )
            result.status = result.score.state

    def run(self) -> ArenaResult:
        repo = str(self.config.repo)
        self._manager = WorktreeManager(repo, base_commit=self.config.commit,
                                        keep=self.config.keep_worktrees)
        try:
            self._profile = self._resolve_profile()
            self._log(f"Repository: {repo} @ {self._manager.base_commit[:12]}")
            self._log(f"Project:    {self._profile.describe()}\n")

            self._run_baseline()

            agents = [self._build_agent(name) for name in self.config.agents]
            self._log(f"Starting {len(agents)} agent(s) x {self.config.runs} run(s)\n")

            jobs: list[tuple[int, AgentAdapter]] = []
            idx = 0
            for agent in agents:
                for run_idx in range(1, self.config.runs + 1):
                    idx += 1
                    jobs.append((idx, agent))

            attempts: list[AgentResult] = []
            if self.config.parallel and len(jobs) > 1:
                with ThreadPoolExecutor(max_workers=min(self.config.max_parallel, len(jobs))) as pool:
                    futures = {pool.submit(self._collect_attempt, agent, i): i for i, agent in jobs}
                    for future in as_completed(futures):
                        attempts.append(future.result())
            else:
                for i, agent in jobs:
                    attempts.append(self._collect_attempt(agent, i))

            attempts.sort(key=lambda r: r.run_index)
            self._finalize(attempts, self.config.weights)

            return ArenaResult(
                task=self.config.task,
                task_file=str(self.config.task_file) if self.config.task_file else None,
                repository=repo,
                base_commit=self._manager.base_commit,
                repo_dirty=self._manager.repo_dirty,
                agents=self.config.agents,
                runs=self.config.runs,
                parallel=self.config.parallel,
                timeout_s=self.config.timeout_s,
                verifiers=list(self.config.verifiers),
                profile=self._profile.to_dict(),
                weights=self.config.weights or {},
                results=attempts,
                agenteval_version=__version__,
            )
        finally:
            self._manager.close()

    def _build_agent(self, name: str) -> AgentAdapter:
        from .agents import AGENT_REGISTRY, create_agent

        config = self.config.agent_configs.get(name)
        if config is None and name not in AGENT_REGISTRY:
            raise ValueError(
                f"unknown agent '{name}'. Configure it in agenteval.yaml "
                f"(agents: section) or use one of: {', '.join(sorted(AGENT_REGISTRY))}"
            )
        return create_agent(name, timeout_s=self.config.timeout_s, config=config)


__all__ = ["ArenaConfig", "ArenaRunner"]
