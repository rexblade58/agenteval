"""AgentEval arena - GitHub issue mode.

Turns a GitHub issue into a reproducible arena task: fetch the title and
body, clone the matching repository, and run the arena against it.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

ISSUE_URL = re.compile(r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)$")


class IssueError(Exception):
    """Raised when an issue cannot be resolved."""


@dataclass
class GithubIssue:
    """A fetched GitHub issue."""

    owner: str
    repo: str
    number: int
    title: str
    body: str
    state: str
    url: str

    @property
    def task_text(self) -> str:
        """Convert the issue into a task prompt for the arena."""
        lines = [self.title.strip()]
        if self.body and self.body.strip():
            lines.append("")
            lines.append(self.body.strip())
        return "\n".join(lines)

    @property
    def clone_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}.git"

    def to_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "repo": self.repo,
            "number": self.number,
            "title": self.title,
            "state": self.state,
            "url": self.url,
        }


def parse_issue_url(url: str) -> tuple[str, str, int]:
    """Validate a GitHub issue URL. Returns (owner, repo, number)."""
    match = ISSUE_URL.match(url.strip())
    if not match:
        raise IssueError(
            f"invalid GitHub issue URL: {url}\n"
            "Expected: https://github.com/<owner>/<repo>/issues/<number>"
        )
    return match.group("owner"), match.group("repo"), int(match.group("number"))


def fetch_issue(url: str, token: str | None = None, timeout: float = 30.0) -> GithubIssue:
    """Fetch an issue via the GitHub REST API.

    Public issues need no token; private issues require ``token``
    (GH_TOKEN environment variable is used when available).
    """
    owner, repo, number = parse_issue_url(url)
    token = token or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = httpx.get(api_url, headers=headers, timeout=timeout)
    if resp.status_code == 404:
        raise IssueError(
            f"issue not found: {url} (repo may be private - set GH_TOKEN)"
        )
    if resp.status_code == 403:
        raise IssueError(f"GitHub API rate limit exceeded or access denied (set GH_TOKEN)")
    if resp.status_code >= 400:
        raise IssueError(f"GitHub API error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    return GithubIssue(
        owner=owner,
        repo=repo,
        number=number,
        title=data.get("title", ""),
        body=data.get("body") or "",
        state=data.get("state", "unknown"),
        url=data.get("html_url", url),
    )


__all__ = ["GithubIssue", "IssueError", "parse_issue_url", "fetch_issue"]
