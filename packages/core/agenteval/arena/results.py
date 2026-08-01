"""AgentEval arena - result artifacts.

Portable result schema (so future community leaderboards can consume
submissions) plus Markdown and HTML report rendering. Nothing is uploaded
anywhere; everything is local unless the user opts in.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agents import AgentRunResult, AgentStatus
from .regression import RegressionReport
from .scoring import ArenaScore
from .verifiers import VerificationResult

SCHEMA_VERSION = 1


@dataclass
class AgentResult:
    """Full record of one agent attempt in an arena run."""

    agent: str
    run_index: int
    status: AgentStatus
    score: ArenaScore | None
    run: AgentRunResult
    tests: VerificationResult | None = None
    build: VerificationResult | None = None
    lint: VerificationResult | None = None
    typecheck: VerificationResult | None = None
    browser: VerificationResult | None = None
    regression: RegressionReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "run_index": self.run_index,
            "status": self.status.value,
            "score": self.score.to_dict() if self.score else None,
            "run": {
                "exit_code": self.run.exit_code,
                "duration_s": round(self.run.duration_s, 3),
                "error": self.run.error,
                "commands_executed": list(self.run.commands_executed),
                "files_changed": list(self.run.files_changed),
                "diff_stat": self.run.diff_stat,
                "token_usage": dict(self.run.token_usage),
                "cost_usd": round(self.run.cost_usd, 6),
            },
            "verification": {
                "tests": self.tests.to_dict() if self.tests else None,
                "build": self.build.to_dict() if self.build else None,
                "lint": self.lint.to_dict() if self.lint else None,
                "typecheck": self.typecheck.to_dict() if self.typecheck else None,
                "browser": self.browser.to_dict() if self.browser else None,
            },
            "regression": self.regression.to_dict() if self.regression else None,
        }


@dataclass
class ArenaResult:
    """Everything about one arena run - fully reproducible."""

    task: str
    task_file: str | None
    repository: str
    base_commit: str
    repo_dirty: bool
    agents: list[str]
    runs: int
    parallel: bool
    timeout_s: int
    verifiers: list[str]
    profile: dict[str, Any]
    weights: dict[str, float]
    sandbox: str = "none"
    results: list[AgentResult] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    agenteval_version: str = "0.1.0"
    environment: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.environment = {
            "os": platform.system(),
            "arch": platform.machine(),
            "python": sys.version.split()[0],
            "hostname": platform.node(),
        }

    @property
    def winner(self) -> AgentResult | None:
        ranked = [r for r in self.results if r.score and r.score.total > 0]
        return max(ranked, key=lambda r: (r.score.total, -r.run.duration_s), default=None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "agenteval_version": self.agenteval_version,
            "started_at": self.started_at,
            "task": {"text": self.task, "file": self.task_file},
            "repository": {
                "source": self.repository,
                "base_commit": self.base_commit,
                "dirty": self.repo_dirty,
            },
            "arena": {
                "agents": list(self.agents),
                "runs": self.runs,
                "parallel": self.parallel,
                "timeout_s": self.timeout_s,
                "verifiers": list(self.verifiers),
                "sandbox": self.sandbox,
            },
            "project": self.profile,
            "scoring": {"weights": dict(self.weights)},
            "environment": dict(self.environment),
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, pretty: bool = True) -> str:
        return json.dumps(self.to_dict(), indent=2 if pretty else None)

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append("# AgentEval Arena Report\n")
        lines.append(f"**Task:** {self.task}\n")
        lines.append(f"**Repository:** {self.repository} @ `{self.base_commit[:12]}`")
        lines.append(f"**Agents:** {', '.join(self.agents)}  ·  **Runs:** {self.runs}  ·  "
                     f"**Parallel:** {self.parallel}")
        lines.append(f"**Project:** {self.profile.get('language', 'unknown')} "
                     f"({self.profile.get('package_manager', 'n/a')})\n")

        if self.results:
            lines.append("## Results\n")
            lines.append("| Rank | Agent | State | Tests | Build | Lint | Type | Regression | Cost | Time | Score |")
            lines.append("|------|-------|-------|-------|-------|------|------|------------|------|------|-------|")
            for idx, r in enumerate(sorted(self.results, key=lambda x: -x.score.total), 1):
                tests = f"{r.tests.passed_commands}/{r.tests.total_commands}" if r.tests and r.tests.total_commands else "-"
                build = "PASS" if (r.build and r.build.passed) else ("FAIL" if (r.build and r.build.total_commands) else "-")
                lint = "PASS" if (r.lint and r.lint.passed) else ("FAIL" if (r.lint and r.lint.total_commands) else "-")
                typecheck = "PASS" if (r.typecheck and r.typecheck.passed) else ("FAIL" if (r.typecheck and r.typecheck.total_commands) else "-")
                regression = str(r.regression.new_failures) if r.regression else "-"
                lines.append(
                    f"| {idx} | {r.agent} | {r.status.value} | {tests} | {build} | {lint} | {typecheck} "
                    f"| {regression} | ${r.run.cost_usd:.4f} | {r.run.duration_s:.0f}s | {r.score.total} |"
                )
            lines.append("")

            winner = self.winner
            if winner:
                lines.append(f"## 🏆 Winner: {winner.agent}\n")
                lines.append(f"Score **{winner.score.total}** with "
                             f"{winner.run.duration_s:.0f}s runtime and ${winner.run.cost_usd:.4f} cost.\n")

        if self.results:
            lines.append("## Details\n")
            for r in self.results:
                lines.append(f"### {r.agent}\n")
                lines.append(f"- State: {r.status.value}")
                lines.append(f"- Exit code: {r.run.exit_code}")
                lines.append(f"- Duration: {r.run.duration_s:.1f}s")
                lines.append(f"- Cost: ${r.run.cost_usd:.6f}")
                if r.run.error:
                    lines.append(f"- Error: {r.run.error}")
                if r.browser and r.browser.error:
                    lines.append(f"- Browser: {r.browser.error}")
                if r.run.files_changed:
                    lines.append(f"- Files changed ({len(r.run.files_changed)}): "
                                 + ", ".join(r.run.files_changed))
                if r.regression:
                    lines.append(f"- Regression: {r.regression.new_failures} new failure(s), "
                                 f"{r.regression.tests_fixed} fixed")
                if r.score.dimensions:
                    lines.append("- Score breakdown:")
                    for d in r.score.dimensions:
                        lines.append(f"  - {d.name}: {d.score:.0%} (weight {d.weight:.0%}) - {d.detail}")
                lines.append("")

        return "\n".join(lines)

    def to_html(self) -> str:
        md = self.to_markdown()
        import html as html_mod

        def _md_escape(text: str) -> str:
            return html_mod.escape(text)

        rows = ""
        for idx, r in enumerate(sorted(self.results, key=lambda x: -x.score.total), 1):
            tests = f"{r.tests.passed_commands}/{r.tests.total_commands}" if r.tests and r.tests.total_commands else "-"
            rows += (
                f"<tr><td>{idx}</td><td>{_md_escape(r.agent)}</td>"
                f"<td>{r.status.value}</td><td>{tests}</td>"
                f"<td>{'PASS' if r.build and r.build.passed else 'FAIL' if r.build and r.build.total_commands else '-'}</td>"
                f"<td>{r.regression.new_failures if r.regression else '-'}</td>"
                f"<td>${r.run.cost_usd:.4f}</td><td>{r.run.duration_s:.0f}s</td>"
                f"<td><strong>{r.score.total}</strong></td></tr>"
            )
        winner = self.winner
        winner_html = (
            f"<h2>Winner: {_md_escape(winner.agent)}</h2>"
            f"<p>Score <strong>{winner.score.total}</strong> in {winner.run.duration_s:.0f}s "
            f"at ${winner.run.cost_usd:.4f}.</p>" if winner else ""
        )
        return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>AgentEval Arena - {_md_escape(self.task[:60])}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem auto; max-width: 960px; color: #0f172a; }}
h1 {{ font-size: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #e2e8f0; padding: .5rem; text-align: left; }}
th {{ background: #f1f5f9; }}
code {{ background: #f1f5f9; padding: 0 .25rem; }}
</style></head>
<body>
<h1>AgentEval Arena Report</h1>
<p><strong>Task:</strong> {_md_escape(self.task)}<br>
<strong>Repository:</strong> {_md_escape(self.repository)} @ <code>{self.base_commit[:12]}</code><br>
<strong>Agents:</strong> {_md_escape(', '.join(self.agents))} · <strong>Runs:</strong> {self.runs}</p>
{winner_html}
<h2>Results</h2>
<table><thead><tr><th>Rank</th><th>Agent</th><th>State</th><th>Tests</th><th>Build</th><th>Regression</th><th>Cost</th><th>Time</th><th>Score</th></tr></thead>
<tbody>{rows}</tbody></table>
<h2>Raw JSON</h2>
<pre>{_md_escape(self.to_json())}</pre>
</body></html>"""


def write_artifacts(result: ArenaResult, run_dir: Path) -> dict[str, Path]:
    """Write report.json, report.md, report.html into a run directory."""
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": run_dir / "report.json",
        "markdown": run_dir / "report.md",
        "html": run_dir / "report.html",
    }
    paths["json"].write_text(result.to_json(), encoding="utf-8")
    paths["markdown"].write_text(result.to_markdown(), encoding="utf-8")
    paths["html"].write_text(result.to_html(), encoding="utf-8")
    return paths


__all__ = ["AgentResult", "ArenaResult", "SCHEMA_VERSION", "write_artifacts"]
