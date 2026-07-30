"""Tests for the AgentEval winning-solution PR creation.

Run with: pytest packages/core/tests
"""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.agents import AgentRunResult, AgentStatus  # noqa: E402
from agenteval.arena.pr import (  # noqa: E402
    PullRequestError,
    build_pr_body,
    create_winner_pr,
    _auth_url,
    _parse_remote,
)
from agenteval.arena.results import ArenaResult  # noqa: E402

GIT = shutil.which("git")


def _sample_result(task: str = "fix the discount") -> ArenaResult:
    from agenteval.arena.scoring import ArenaScore, DimensionScore

    result = ArenaResult(
        task=task,
        task_file=None,
        repository="https://github.com/octocat/Hello-World.git",
        base_commit="abc123def456",
        repo_dirty=False,
        agents=["fixer"],
        runs=1,
        parallel=False,
        timeout_s=60,
        verifiers=["tests"],
        profile={"language": "python"},
        weights={},
    )
    score = ArenaScore(total=96.0, state=AgentStatus.PASS,
                       dimensions=[DimensionScore("functional", 0.5, 1.0, "tests pass")])
    run = AgentRunResult(
        agent="fixer",
        status=AgentStatus.PASS,
        exit_code=0,
        duration_s=42.0,
        cost_usd=0.31,
        files_changed=["app/__init__.py"],
        git_diff="--- a/app/__init__.py\n+++ b/app/__init__.py\n@@ -1,3 +1,3 @@\n-> 100\n+> 50\n",
    )
    result.results.append(type(
        "AR", (object,),
        {
            "agent": "fixer",
            "status": AgentStatus.PASS,
            "score": score,
            "run": run,
            "tests": None,
            "build": None,
            "lint": None,
            "typecheck": None,
            "regression": None,
        },
    )())
    return result


class TestPrBody:
    def test_build_pr_body_has_evidence(self):
        body = build_pr_body(_sample_result())
        assert "AgentEval Arena Result" in body
        assert "Starting commit" in body
        assert "fixer" in body
        assert "96.0" in body
        assert "app/__init__.py" in body
        assert "AgentEval" in body


class TestRemoteParsing:
    def test_parse_https(self):
        owner, repo, base = _parse_remote("https://github.com/octocat/Hello-World.git", None)
        assert (owner, repo, base) == ("octocat", "Hello-World", "main")

    def test_parse_ssh(self):
        owner, repo, base = _parse_remote("git@github.com:octocat/Hello-World.git", "develop")
        assert (owner, repo, base) == ("octocat", "Hello-World", "develop")

    def test_auth_url_https(self):
        url = _auth_url("https://github.com/octocat/Hello-World.git", "tok")
        assert "x-access-token:tok@" in url

    def test_auth_url_ssh(self):
        url = _auth_url("git@github.com:octocat/Hello-World.git", "tok")
        assert url.startswith("https://x-access-token:tok@github.com/octocat/Hello-World.git")


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestCreatePr:
    def _init_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@agenteval.dev"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AgentEval Test"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "remote", "add", "origin", "https://github.com/octocat/Hello-World.git"],
                       cwd=repo, check=True, capture_output=True)
        (repo / "app.py").write_text("x = 100\n", encoding="utf-8")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True, capture_output=True)
        return repo

    def test_create_winner_pr_flow(self, tmp_path):
        repo = self._init_repo(tmp_path)
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True, check=True).stdout.strip()
        result = _sample_result()
        result.base_commit = head
        # match the fixture file layout: diff must apply to app.py
        result.results[0].run.git_diff = (
            "--- a/app.py\n+++ b/app.py\n@@ -1 +1 @@\n-x = 100\n+x = 50\n"
        )

        fake_resp = mock.Mock()
        fake_resp.status_code = 201
        fake_resp.json.return_value = {"html_url": "https://github.com/octocat/Hello-World/pull/7"}

        with mock.patch.dict("os.environ", {"GH_TOKEN": "tok"}):
            with mock.patch("httpx.post", return_value=fake_resp) as post:
                with mock.patch("agenteval.arena.pr._push_branch", return_value=True) as push:
                    url = create_winner_pr(result, repo)

        assert url == "https://github.com/octocat/Hello-World/pull/7"
        push.assert_called_once()
        post.assert_called_once()
        _, kwargs = post.call_args
        payload = kwargs["json"]
        assert payload["head"].startswith("agenteval/fixer-")
        assert payload["base"] == "main"
        assert "AgentEval Arena Result" in payload["body"]

        # The branch was created and committed locally
        branches = subprocess.run(["git", "branch", "--list", "agenteval/*"],
                                  cwd=repo, capture_output=True, text=True, check=True)
        assert "agenteval/fixer-" in branches.stdout
        # The patch was applied and committed on the branch
        content = subprocess.run(["git", "show", f"{payload['head']}:app.py"],
                                 cwd=repo, capture_output=True, text=True, check=True)
        assert "x = 50" in content.stdout
        # Original checkout restored
        branch_now = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                    cwd=repo, capture_output=True, text=True, check=True)
        assert branch_now.stdout.strip() == "main"

    def test_create_pr_requires_token(self, tmp_path):
        repo = self._init_repo(tmp_path)
        with mock.patch.dict("os.environ", {}, clear=True):
            with pytest.raises(PullRequestError):
                create_winner_pr(_sample_result(), repo)

    def test_no_remote_raises(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, capture_output=True)
        with mock.patch.dict("os.environ", {"GH_TOKEN": "tok"}):
            with pytest.raises(PullRequestError):
                create_winner_pr(_sample_result(), repo)
