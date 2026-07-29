"""Tests for the AgentEval GitHub issue mode.

Run with: pytest packages/core/tests
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.github import build_comment  # noqa: E402
from agenteval.arena.issues import (  # noqa: E402
    IssueError,
    fetch_issue,
    parse_issue_url,
)


class TestIssueUrl:
    def test_valid_url(self):
        owner, repo, number = parse_issue_url(
            "https://github.com/octocat/Hello-World/issues/42"
        )
        assert (owner, repo, number) == ("octocat", "Hello-World", 42)

    def test_invalid_url(self):
        for bad in (
            "https://github.com/octocat/Hello-World",
            "https://github.com/octocat/Hello-World/pull/42",
            "not-a-url",
        ):
            try:
                parse_issue_url(bad)
                assert False, f"should have raised for {bad}"
            except IssueError:
                pass


class TestFetchIssue:
    def test_fetch_public_issue(self):
        payload = {
            "title": "Checkout discount broken",
            "body": "Discount applies over $100 instead of $50.",
            "state": "open",
            "html_url": "https://github.com/octocat/Hello-World/issues/42",
        }
        fake = mock.Mock()
        fake.status_code = 200
        fake.json.return_value = payload

        with mock.patch("httpx.get", return_value=fake) as get:
            issue = fetch_issue("https://github.com/octocat/Hello-World/issues/42")

        get.assert_called_once()
        assert issue.owner == "octocat"
        assert issue.number == 42
        assert issue.title == "Checkout discount broken"
        assert "Discount applies over $100" in issue.task_text

    def test_fetch_404_raises(self):
        fake = mock.Mock()
        fake.status_code = 404
        with mock.patch("httpx.get", return_value=fake):
            try:
                fetch_issue("https://github.com/octocat/Hello-World/issues/42")
                assert False, "should have raised"
            except IssueError as exc:
                assert "not found" in str(exc)

    def test_fetch_uses_token_env(self):
        fake = mock.Mock()
        fake.status_code = 200
        fake.json.return_value = {"title": "t", "body": "", "state": "open"}

        with mock.patch.dict("os.environ", {"GH_TOKEN": "secret-token"}):
            with mock.patch("httpx.get", return_value=fake) as get:
                fetch_issue("https://github.com/octocat/Hello-World/issues/42")

        _, kwargs = get.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer secret-token"


class TestGithubComment:
    def _sample_result(self):
        from agenteval.arena.results import ArenaResult
        from agenteval.arena.scoring import ArenaScore, DimensionScore
        from agenteval.arena.agents import AgentRunResult, AgentStatus

        result = ArenaResult(
            task="fix the discount",
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
        score = ArenaScore(
            total=96.0,
            state=AgentStatus.PASS,
            dimensions=[DimensionScore("functional", 0.5, 1.0, "tests pass")],
        )
        run = AgentRunResult(
            agent="fixer",
            status=AgentStatus.PASS,
            exit_code=0,
            duration_s=42.0,
            cost_usd=0.31,
        )
        from agenteval.arena.verifiers import VerificationResult

        result.results.append(type(
            "AR", (object,),
            {
                "agent": "fixer",
                "status": AgentStatus.PASS,
                "score": score,
                "run": run,
                "tests": VerificationResult("tests", True, 1, 1),
                "build": None,
                "lint": None,
                "typecheck": None,
                "regression": None,
            },
        )())
        return result

    def test_build_comment_has_evidence(self):
        comment = build_comment(self._sample_result())
        assert "AgentEval Arena Result" in comment
        assert "fixer" in comment
        assert "96.0" in comment
        assert "abc123" in comment

    def test_post_issue_comment_requires_token(self):
        from agenteval.arena.github import ReportError, post_issue_comment

        with mock.patch.dict("os.environ", {}, clear=True):
            try:
                post_issue_comment("o", "r", 1, "body")
                assert False, "should have raised"
            except ReportError:
                pass

    def test_post_issue_comment_posts(self):
        from agenteval.arena.github import post_issue_comment

        fake = mock.Mock()
        fake.status_code = 201
        fake.json.return_value = {"html_url": "https://github.com/o/r/issues/1#issuecomment-9"}

        with mock.patch.dict("os.environ", {"GH_TOKEN": "t"}):
            with mock.patch("httpx.post", return_value=fake) as post:
                url = post_issue_comment("o", "r", 1, "body text")

        assert url == "https://github.com/o/r/issues/1#issuecomment-9"
        _, kwargs = post.call_args
        assert kwargs["json"]["body"] == "body text"
