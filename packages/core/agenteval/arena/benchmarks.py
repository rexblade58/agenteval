"""AgentEval arena - community benchmark packs.

A benchmark pack bundles a repository + a sequence of tasks into a named,
reproducible benchmark that can be run against any installed agents.

Pack layout::

    my-pack/
    ├── agenteval-benchmark.yaml   # manifest (required)
    └── ...                        # optional fixture repo (if repo: is local)

Manifest format::

    name: checkout-discount
    description: Fix checkout discount calculation
    repo: https://github.com/user/project   # git URL or local path
    commit: main                            # optional starting ref/commit
    tasks:
      - "Fix the checkout discount calculation"
      - "Add a regression test for multiple products"
    agents: [codex, claude]
    runs: 1
    timeout: 900
    parallel: false
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore[assignment]

MANIFEST_NAME = "agenteval-benchmark.yaml"
DEFAULT_PACKS_DIR = "benchmarks"


class BenchmarkError(Exception):
    """Raised when a pack cannot be loaded or run."""


@dataclass
class BenchmarkPack:
    """A named benchmark: a repository plus a sequence of tasks."""

    name: str
    description: str
    repo: str
    tasks: list[str] = field(default_factory=list)
    agents: list[str] = field(default_factory=list)
    runs: int = 1
    timeout: int = 900
    parallel: bool = False
    commit: str | None = None
    source: str = ""  # where the pack was loaded from

    @classmethod
    def from_manifest(cls, data: dict[str, Any], source: str) -> "BenchmarkPack":
        name = str(data.get("name") or "").strip()
        if not name:
            raise BenchmarkError(f"benchmark manifest at {source} is missing 'name'")
        repo = str(data.get("repo") or "").strip()
        if not repo:
            raise BenchmarkError(f"benchmark pack '{name}' is missing 'repo'")
        return cls(
            name=name,
            description=str(data.get("description") or "").strip(),
            repo=repo,
            tasks=[str(t) for t in (data.get("tasks") or [])],
            agents=[str(a) for a in (data.get("agents") or [])],
            runs=int(data.get("runs") or 1),
            timeout=int(data.get("timeout") or 900),
            parallel=bool(data.get("parallel", False)),
            commit=data.get("commit"),
            source=source,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "repo": self.repo,
            "tasks": list(self.tasks),
            "agents": list(self.agents),
            "runs": self.runs,
            "timeout": self.timeout,
            "parallel": self.parallel,
            "commit": self.commit,
            "source": self.source,
        }


def load_pack(path: Path) -> BenchmarkPack:
    """Load a pack from a directory containing the manifest."""
    manifest = path / MANIFEST_NAME
    if not manifest.is_file():
        raise BenchmarkError(f"no {MANIFEST_NAME} in {path}")
    if yaml is None:  # pragma: no cover
        raise BenchmarkError("PyYAML is required to load benchmark packs")
    data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkError(f"invalid manifest in {manifest}")
    return BenchmarkPack.from_manifest(data, source=str(path))


def discover_packs(packs_dir: Path | None = None) -> list[BenchmarkPack]:
    """Find packs in the local packs directory (default: ./benchmarks)."""
    base = packs_dir or Path(DEFAULT_PACKS_DIR)
    if not base.is_dir():
        return []
    packs: list[BenchmarkPack] = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / MANIFEST_NAME).is_file():
            try:
                packs.append(load_pack(child))
            except BenchmarkError:
                continue
    return packs


def install_pack(source: str, packs_dir: Path | None = None) -> Path:
    """Install a pack from a local directory or git URL into packs_dir."""
    base = packs_dir or Path(DEFAULT_PACKS_DIR)
    base.mkdir(parents=True, exist_ok=True)

    if source.startswith(("https://", "http://", "git@", "ssh://", "git://")):
        name = source.rstrip("/").split("/")[-1].replace(".git", "")
        target = base / name
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
        import subprocess

        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", source, str(target)],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            raise BenchmarkError(f"clone failed: {result.stderr.strip()[:200]}")
        # The pack may be nested under benchmarks/ inside the cloned repo
        nested = target / DEFAULT_PACKS_DIR
        if nested.is_dir() and (nested / MANIFEST_NAME).is_file():
            return nested
        return target

    src = Path(source).resolve()
    if not src.is_dir():
        raise BenchmarkError(f"not a directory: {source}")
    if not (src / MANIFEST_NAME).is_file():
        raise BenchmarkError(f"no {MANIFEST_NAME} in {source}")
    target = base / src.name
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(src, target)
    return target


__all__ = ["BenchmarkPack", "BenchmarkError", "load_pack", "discover_packs", "install_pack",
           "MANIFEST_NAME", "DEFAULT_PACKS_DIR"]
