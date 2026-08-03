"""Tests for AgentEval benchmark packs.

Run with: pytest packages/core/tests
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.benchmarks import (  # noqa: E402
    BenchmarkError,
    discover_packs,
    install_pack,
    load_pack,
)

GIT = shutil.which("git")
PYTHON_APP = Path(__file__).resolve().parent / "fixtures" / "python-app"


def _write_pack(base: Path, name: str = "test-pack") -> Path:
    pack_dir = base / name
    (pack_dir / "repo").mkdir(parents=True)
    shutil.copytree(PYTHON_APP, pack_dir / "repo" / "app", dirs_exist_ok=True)
    (pack_dir / "agenteval-benchmark.yaml").write_text(
        "name: test-pack\n"
        "description: A test pack\n"
        "repo: ./repo\n"
        "tasks:\n"
        '  - "Fix the bug"\n'
        "agents: [fixer]\n"
        "timeout: 60\n",
        encoding="utf-8",
    )
    return pack_dir


class TestManifest:
    def test_load_pack(self, tmp_path):
        pack_dir = _write_pack(tmp_path)
        pack = load_pack(pack_dir)
        assert pack.name == "test-pack"
        assert pack.repo == "./repo"
        assert pack.tasks == ["Fix the bug"]
        assert pack.agents == ["fixer"]
        assert pack.timeout == 60

    def test_missing_manifest_raises(self, tmp_path):
        with pytest.raises(BenchmarkError):
            load_pack(tmp_path / "empty")

    def test_missing_name_raises(self, tmp_path):
        (tmp_path / "p").mkdir()
        (tmp_path / "p" / "agenteval-benchmark.yaml").write_text(
            "repo: ./x\n", encoding="utf-8"
        )
        with pytest.raises(BenchmarkError):
            load_pack(tmp_path / "p")

    def test_missing_repo_raises(self, tmp_path):
        (tmp_path / "p").mkdir()
        (tmp_path / "p" / "agenteval-benchmark.yaml").write_text(
            "name: nope\n", encoding="utf-8"
        )
        with pytest.raises(BenchmarkError):
            load_pack(tmp_path / "p")


class TestDiscover:
    def test_discovers_packs(self, tmp_path):
        _write_pack(tmp_path / "benchmarks")
        (tmp_path / "benchmarks" / "not-a-pack").mkdir()
        packs = discover_packs(tmp_path / "benchmarks")
        assert len(packs) == 1
        assert packs[0].name == "test-pack"

    def test_empty_dir(self, tmp_path):
        assert discover_packs(tmp_path / "nope") == []


@pytest.mark.skipif(GIT is None, reason="git not installed")
class TestInstall:
    def test_install_from_directory(self, tmp_path):
        src = _write_pack(tmp_path / "src")
        target = install_pack(str(src), tmp_path / "packs")
        assert (target / "agenteval-benchmark.yaml").is_file()
        assert discover_packs(tmp_path / "packs")[0].name == "test-pack"

    def test_install_missing_dir_raises(self, tmp_path):
        with pytest.raises(BenchmarkError):
            install_pack(str(tmp_path / "nope"), tmp_path / "packs")

    def test_install_plain_dir_raises(self, tmp_path):
        (tmp_path / "plain").mkdir()
        with pytest.raises(BenchmarkError):
            install_pack(str(tmp_path / "plain"), tmp_path / "packs")


class TestCli:
    @pytest.mark.skipif(GIT is None, reason="git not installed")
    def test_benchmark_list_cli(self, tmp_path):
        packs = tmp_path / "packs"
        _write_pack(packs)
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [sys.executable, "-m", "agenteval.cli", "benchmark", "list", "--dir", str(packs)],
            capture_output=True, text=True, env=env, cwd=tmp_path,
        )
        assert proc.returncode == 0
        assert "test-pack" in proc.stdout
        assert "A test pack" in proc.stdout

    def test_benchmark_list_empty(self, tmp_path):
        env = dict(__import__("os").environ)
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
        proc = subprocess.run(
            [sys.executable, "-m", "agenteval.cli", "benchmark", "list", "--dir", str(tmp_path)],
            capture_output=True, text=True, env=env, cwd=tmp_path,
        )
        assert proc.returncode == 0
        assert "No benchmark packs" in proc.stdout
