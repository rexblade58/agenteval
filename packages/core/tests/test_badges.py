"""Tests for AgentEval badges and the verify command.

Run with: pytest packages/core/tests
"""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.badges import (  # noqa: E402
    markdown_snippet,
    verified_badge,
    winner_badge,
    write_badge,
)
from agenteval.arena.verify import all_passed, summary, verify_project  # noqa: E402

GIT = __import__("shutil").which("git")


class TestBadges:
    def test_verified_badge_green(self):
        svg = verified_badge(True)
        assert "AgentEval" in svg
        assert "Verified" in svg
        assert "4c1" in svg  # green fill
        assert "<svg" in svg

    def test_failed_badge_red(self):
        svg = verified_badge(False)
        assert "Failed" in svg
        assert "e05d44" in svg  # red fill

    def test_winner_badge(self):
        from agenteval.arena.results import ArenaResult
        from agenteval.arena.scoring import ArenaScore
        from agenteval.arena.agents import AgentRunResult, AgentStatus

        result = ArenaResult(
            task="t", task_file=None, repository="r", base_commit="abc",
            repo_dirty=False, agents=["codex"], runs=1, parallel=False,
            timeout_s=60, verifiers=["tests"], profile={}, weights={},
        )
        result.results.append(type(
            "AR", (object,),
            {
                "agent": "codex",
                "status": AgentStatus.PASS,
                "score": ArenaScore(total=96.0, state=AgentStatus.PASS),
                "run": AgentRunResult(agent="codex", status=AgentStatus.PASS, duration_s=10),
                "tests": None, "build": None, "lint": None, "typecheck": None,
                "browser": None, "regression": None,
            },
        )())
        svg = winner_badge(result)
        assert "Winner: codex" in svg
        assert "96.0" in svg

    def test_no_winner_badge(self):
        from agenteval.arena.results import ArenaResult

        result = ArenaResult(
            task="t", task_file=None, repository="r", base_commit="abc",
            repo_dirty=False, agents=["codex"], runs=1, parallel=False,
            timeout_s=60, verifiers=["tests"], profile={}, weights={},
        )
        svg = winner_badge(result)
        assert "no winner" in svg

    def test_write_and_markdown(self, tmp_path):
        out = tmp_path / "badges" / "agenteval.svg"
        write_badge(verified_badge(True), out)
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("<svg")
        assert "[![AgentEval]" in markdown_snippet("badges/agenteval.svg")


class TestVerify:
    def test_verify_fixture_app(self):
        fixture = Path(__file__).resolve().parent / "fixtures" / "python-app"
        results = verify_project(fixture, timeout_s=120)
        text = summary(results)
        assert "Verification results" in text
        # The fixture has failing tests at baseline
        assert not all_passed(results)
        assert "FAIL" in text

    def test_verify_missing_dir(self, tmp_path):
        with pytest.raises(OSError):
            verify_project(tmp_path / "nope")

    @pytest.mark.skipif(GIT is None, reason="git not installed")
    def test_verify_cli(self, tmp_path):
        fixture = Path(__file__).resolve().parent / "fixtures" / "python-app"
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [sys.executable, "-m", "agenteval.cli", "verify",
             "--repo", str(fixture), "--timeout", "120", "--badge", "verified.svg"],
            capture_output=True, text=True, env=env, cwd=tmp_path,
        )
        assert proc.returncode == 2  # fixture has failing tests
        assert "Verification results" in proc.stdout
        assert (tmp_path / "verified.svg").exists()
        assert "README snippet" in proc.stdout
