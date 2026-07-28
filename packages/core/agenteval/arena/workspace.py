"""AgentEval arena - isolated repository workspaces.

Uses git worktrees so every competing agent gets a lightweight, isolated
copy of the exact same starting commit. The original repository is never
modified.
"""

from __future__ import annotations

import re
import shutil
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from .exec import ExecResult, run_command

GIT_STATUS_PORCELAIN = re.compile(r"^([ MADRCU?!]{2})\s+(.*)$", re.MULTILINE)


@dataclass
class DiffSummary:
    """What an agent changed in its workspace."""

    files_changed: list[str] = field(default_factory=list)
    diff_stat: str = ""
    git_diff: str = ""


class WorkspaceError(Exception):
    """Raised when a repository cannot be prepared."""


class WorktreeManager:
    """Creates and cleans up isolated worktrees from a source repository.

    ``repo`` may be a local path or a git URL. For remote URLs the
    repository is cloned once into a temp directory; local repositories are
    used in place (only worktrees are created, never checked out).
    """

    def __init__(self, repo: str | Path, base_commit: str | None = None, keep: bool = False):
        self.keep = keep
        self._temp_root: Path | None = None
        self._local_repo: Path | None = None
        self._worktrees: list[Path] = []
        self._lock = threading.Lock()
        self._counter = 0
        self.repo_dirty: bool = False

        if self._looks_like_url(repo):
            self._local_repo, self._temp_root = self._clone(repo)
        else:
            self._local_repo = Path(repo).resolve()
            if not (self._local_repo / ".git").exists() and not (self._local_repo / ".git").is_file():
                raise WorkspaceError(f"not a git repository: {self._local_repo}")

        self.base_commit = base_commit or self._resolve_head()
        self.original_head = self._resolve_head()
        self._check_dirty()

    @staticmethod
    def _looks_like_url(repo: str | Path) -> bool:
        text = str(repo)
        return text.startswith(("https://", "http://", "git@", "ssh://", "git://"))

    def _run(self, args: list[str]) -> ExecResult:
        return run_command(["git", *args], self._local_repo or Path.cwd(), 60)

    def _resolve_head(self) -> str:
        result = self._run(["rev-parse", "HEAD"])
        if not result.ok:
            raise WorkspaceError(f"cannot resolve HEAD: {result.stderr.strip()}")
        return result.stdout.strip()

    def _check_dirty(self) -> None:
        if self._local_repo is None:
            return
        result = self._run(["status", "--porcelain"])
        self.repo_dirty = bool(result.stdout.strip())
        if self.repo_dirty:
            import sys

            print(
                f"warning: repository has uncommitted changes; arena starts from {self.base_commit[:12]}",
                file=sys.stderr,
            )

    def _clone(self, url: str) -> tuple[Path, Path]:
        root = Path(tempfile.mkdtemp(prefix="agenteval-clone-"))
        result = run_command(["git", "clone", "--quiet", url, str(root / "repo")], root, 600)
        if not result.ok:
            shutil.rmtree(root, ignore_errors=True)
            raise WorkspaceError(f"clone failed: {result.stderr.strip() or result.stdout.strip()}")
        return root / "repo", root

    def create(self, label: str) -> Path:
        """Create a detached worktree at the base commit. Returns its path."""
        if self._local_repo is None:
            raise WorkspaceError("no repository")
        root = self._local_repo.parent / f".agenteval-worktrees-{self._local_repo.name}"
        root.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._counter += 1
            index = self._counter
        target = root / f"{label}-{index}"
        result = run_command(
            ["git", "worktree", "add", "--detach", str(target), self.base_commit],
            self._local_repo,
            120,
        )
        if not result.ok:
            raise WorkspaceError(f"worktree add failed: {result.stderr.strip()}")
        with self._lock:
            self._worktrees.append(target)
        return target

    def diff(self, workspace: Path) -> DiffSummary:
        """Capture the agent's changes relative to the base commit."""
        status = run_command(["git", "status", "--porcelain"], workspace, 60)
        names: list[str] = []
        for match in GIT_STATUS_PORCELAIN.finditer(status.stdout):
            path = match.group(2).strip()
            if path and not path.startswith(".agenteval"):
                names.append(path)

        stat = run_command(["git", "diff", "--stat", self.base_commit, "--", "."], workspace, 60)
        full = run_command(["git", "diff", self.base_commit, "--", "."], workspace, 60)
        return DiffSummary(
            files_changed=sorted(set(names)),
            diff_stat=stat.stdout.strip(),
            git_diff=full.stdout.strip(),
        )

    def cleanup(self, workspace: Path | None = None) -> None:
        """Remove a worktree (all tracked ones when None)."""
        if self._local_repo is None:
            return
        with self._lock:
            targets = [workspace] if workspace else list(self._worktrees)
        for target in targets:
            if target is None:
                continue
            run_command(["git", "worktree", "remove", "--force", str(target)], self._local_repo, 60)
            with self._lock:
                if target in self._worktrees:
                    self._worktrees.remove(target)
            shutil.rmtree(target, ignore_errors=True)

    def close(self) -> None:
        """Remove all worktrees and the temp clone (unless --keep)."""
        self.cleanup()
        if self._temp_root and not self.keep:
            shutil.rmtree(self._temp_root, ignore_errors=True)


__all__ = ["DiffSummary", "WorkspaceError", "WorktreeManager"]
