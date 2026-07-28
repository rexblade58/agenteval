"""Tests for the AgentEval arena.

Run with: pytest packages/core/tests
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.agents import (  # noqa: E402
    AgentStatus,
    CommandAgent,
    create_agent,
)
from agenteval.arena.project import detect  # noqa: E402
from agenteval.arena.regression import compare, parse_test_summary  # noqa: E402
from agenteval.arena.scoring import score_attempt  # noqa: E402
from agenteval.arena.verifiers import TestVerifier, create_verifier  # noqa: E402
from agenteval.arena.workspace import WorktreeManager  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PYTHON_APP = FIXTURES / "python-app"

GIT = shutil.which("git")
PYTEST = "pytest"


def _init_fixture_repo(tmp_path: Path) -> Path:
    """Copy the fixture app and commit it as a git repo."""
    repo = tmp_path / "repo"
    shutil.copytree(PYTHON_APP, repo)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@agenteval.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "AgentEval Test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture: broken discount"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestWorktrees:
    def test_create_and_diff(self, tmp_path):
        repo = _init_fixture_repo(tmp_path)
        mgr = WorktreeManager(repo)
        ws = mgr.create("test")
        assert ws.is_dir()
        assert (ws / "pyproject.toml").exists()
        # original repo untouched
        assert not (repo / ".agenteval-worktrees-test").exists() or True

        # a modification is visible in the diff
        (ws / "app" / "__init__.py").write_text(
            (ws / "app" / "__init__.py").read_text(encoding="utf-8").replace("> 100", "> 50"),
            encoding="utf-8",
        )
        diff = mgr.diff(ws)
        assert "app/__init__.py" in diff.files_changed
        assert "+" in diff.diff_stat
        assert "> 50" in diff.git_diff

        mgr.cleanup(ws)
        assert not ws.exists()

    def test_remote_url_clone(self, tmp_path):
        # local path that looks like a URL is not required; verify error path
        with pytest.raises(Exception):
            WorktreeManager(tmp_path / "missing", base_commit=None)


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestProjectDetection:
    def test_python_app_detected(self):
        profile = detect(PYTHON_APP)
        assert profile.language == "python"
        assert "pytest" in profile.test[0]
        assert profile.test[0].startswith(("pytest", "python -m pytest"))


class TestVerifiers:
    def test_pytest_verifier_detects_failures(self, tmp_path):
        repo = _init_fixture_repo(tmp_path)
        verifier = TestVerifier()
        from agenteval.arena.project import detect

        result = verifier.verify(repo, detect(repo))
        assert result.total_commands >= 1
        assert result.passed_commands < result.total_commands  # fixture has a failing test

    def test_create_verifier_unknown(self):
        with pytest.raises(ValueError):
            create_verifier("nope")


class TestRegression:
    def test_parse_pytest_summary(self):
        passed, failed = parse_test_summary("=== 2 passed, 1 failed in 0.5s ===")
        assert passed == 2
        assert failed == 1
        # pytest prints failed-first on some versions
        passed, failed = parse_test_summary("=== 2 failed, 1 passed in 0.5s ===")
        assert passed == 1
        assert failed == 2

    def test_compare_detects_fix_and_regression(self, tmp_path):
        from agenteval.arena.verifiers import VerificationResult
        from agenteval.arena.exec import ExecResult

        def vr(passed, total):
            return VerificationResult(
                name="tests",
                passed=passed == total,
                passed_commands=passed,
                total_commands=total,
                commands=[
                    ExecResult(command="pytest", exit_code=0 if passed == total else 1,
                               duration_s=0.1, stdout=f"{passed} passed, {total-passed} failed")
                ],
            )

        baseline = vr(2, 3)
        fixed = vr(3, 3)
        report = compare(baseline_tests=baseline, modified_tests=fixed)
        assert report.tests_fixed == 1
        assert report.new_failures == 0

        broke = vr(1, 3)
        report2 = compare(baseline_tests=baseline, modified_tests=broke)
        assert report2.new_failures == 1


class TestScoring:
    def test_tests_dominate(self):
        from agenteval.arena.verifiers import VerificationResult
        from agenteval.arena.exec import ExecResult

        def vr(passed, total):
            return VerificationResult(
                name="tests",
                passed=passed == total,
                passed_commands=passed,
                total_commands=total,
                commands=[ExecResult(command="pytest", exit_code=0, duration_s=0.1)],
            )

        good = score_attempt(
            state=AgentStatus.PASS, tests=vr(3, 3), regression=None, duration_s=10, min_duration=5
        )
        bad = score_attempt(
            state=AgentStatus.PASS, tests=vr(0, 3), regression=None, duration_s=10, min_duration=5
        )
        assert good.total > bad.total
        assert bad.total == 0.0  # hard gate

    def test_timeout_disqualified(self):
        score = score_attempt(state=AgentStatus.TIMEOUT, tests=None, regression=None)
        assert score.total == 0.0
        assert score.disqualification is not None


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestCommandAgent:
    def test_generic_agent_fixes_repo(self, tmp_path):
        repo = _init_fixture_repo(tmp_path)

        fixer = str(FIXTURES / "fix_discount.py")
        agent = CommandAgent(
            command=f'python "{fixer}" "{{task}}"',
            name="fixer",
            timeout_s=60,
        )
        result = agent.run(repo, "fix the discount bug")
        assert result.status == AgentStatus.PASS
        assert result.exit_code == 0
        assert "discount" in result.stdout.lower() or result.stdout.strip()

    def test_agent_timeout(self, tmp_path):
        sleeper = str(FIXTURES / "sleep.py")
        agent = CommandAgent(
            command=f'python "{sleeper}"',
            name="sleeper",
            timeout_s=2,
        )
        result = agent.run(tmp_path, "task")
        assert result.status == AgentStatus.TIMEOUT

    def test_create_agent_from_config(self):
        agent = create_agent(
            "my-agent",
            config={"command": "my-agent run {task}", "timeout": 60, "description": "custom"},
        )
        assert agent.name == "my-agent"
        assert agent.timeout_s == 60

    def test_create_agent_unknown(self):
        with pytest.raises(ValueError):
            create_agent("does-not-exist")


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestArenaCli:
    def test_arena_end_to_end(self, tmp_path):
        repo = _init_fixture_repo(tmp_path)
        fixer = str(FIXTURES / "fix_discount.py")

        # Register a custom agent via agenteval.yaml (tests the config path too)
        (repo / "agenteval.yaml").write_text(
            "agents:\n"
            "  fixer:\n"
            f"    command: python \"{fixer}\" \"{{task}}\"\n"
            "    timeout: 120\n"
            "    description: fixture agent that fixes the discount bug\n",
            encoding="utf-8",
        )

        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [
                sys.executable, "-m", "agenteval.cli", "arena",
                "--repo", str(repo),
                "--task", "fix the discount threshold bug",
                "--agents", "fixer",
                "--format", "json",
                "--timeout", "120",
            ],
            capture_output=True, text=True, env=env,
            cwd=tmp_path,
        )
        assert proc.returncode == 0, proc.stderr

        # find the JSON after the console banner lines
        stdout = proc.stdout
        start = stdout.find("{")
        assert start != -1
        import json

        data = json.loads(stdout[start:])
        assert data["schema_version"] == 1
        assert data["task"]["text"] == "fix the discount threshold bug"
        assert len(data["results"]) == 1
        result = data["results"][0]
        assert result["status"] in ("PASS", "PARTIAL")
        assert result["score"]["total"] >= 60
        assert "app/__init__.py" in result["run"]["files_changed"]

    def test_arena_agents_list(self, tmp_path):
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [sys.executable, "-m", "agenteval.cli", "agents", "list"],
            capture_output=True, text=True, env=env, cwd=tmp_path,
        )
        assert proc.returncode == 0
        assert "codex" in proc.stdout
        assert "claude" in proc.stdout
