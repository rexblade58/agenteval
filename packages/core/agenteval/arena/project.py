"""AgentEval arena - automatic project detection.

Detects common ecosystems from manifest files and infers sensible default
install/test/build/lint/typecheck commands. Detection is a starting point:
explicit configuration always overrides it.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10
    tomllib = None  # type: ignore[assignment]


@dataclass
class ProjectProfile:
    """Inferred or configured verification plan for a project."""

    language: str = "unknown"
    package_manager: str | None = None
    install: list[str] = field(default_factory=list)
    test: list[str] = field(default_factory=list)
    build: list[str] = field(default_factory=list)
    lint: list[str] = field(default_factory=list)
    typecheck: list[str] = field(default_factory=list)
    detected_by: str = ""

    def to_dict(self) -> dict[str, Any]:
        return dataclass_dict(self)

    def describe(self) -> str:
        parts = [f"language={self.language}"]
        if self.package_manager:
            parts.append(f"package_manager={self.package_manager}")
        if self.install:
            parts.append(f"install={'; '.join(self.install)}")
        if self.test:
            parts.append(f"test={'; '.join(self.test)}")
        if self.build:
            parts.append(f"build={'; '.join(self.build)}")
        if self.lint:
            parts.append(f"lint={'; '.join(self.lint)}")
        if self.typecheck:
            parts.append(f"typecheck={'; '.join(self.typecheck)}")
        return ", ".join(parts)


def dataclass_dict(profile: ProjectProfile) -> dict[str, Any]:
    return {
        "language": profile.language,
        "package_manager": profile.package_manager,
        "install": list(profile.install),
        "test": list(profile.test),
        "build": list(profile.build),
        "lint": list(profile.lint),
        "typecheck": list(profile.typecheck),
        "detected_by": profile.detected_by,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _read_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:  # pragma: no cover - Python 3.10 fallback
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _python_cmd(tool: str) -> str:
    """Use `python -m tool` when the tool is not on PATH (common on Windows)."""
    if shutil.which(tool):
        return tool
    return f"python -m {tool}"


def detect(workspace: Path) -> ProjectProfile:
    """Detect the project type from manifest files in the workspace root."""
    files = {p.name for p in workspace.iterdir() if p.is_file()}

    if "package.json" in files:
        pkg = _read_json(workspace / "package.json")
        scripts = pkg.get("scripts", {})
        profile = ProjectProfile(language="javascript")
        if "pnpm-lock.yaml" in files:
            profile.package_manager = "pnpm"
            profile.install = ["pnpm install"]
            profile.test = ["pnpm test"] if "test" in scripts else []
        elif "yarn.lock" in files:
            profile.package_manager = "yarn"
            profile.install = ["yarn install"]
            profile.test = ["yarn test"] if "test" in scripts else []
        else:
            profile.package_manager = "npm"
            profile.install = ["npm install"]
            profile.test = ["npm test"] if "test" in scripts else []
        if scripts.get("build"):
            profile.build = ["npm run build"] if profile.package_manager == "npm" else [f"{profile.package_manager} build"]
        if scripts.get("lint"):
            profile.lint = [f"{profile.package_manager} run lint"]
        if "tsconfig.json" in files:
            profile.typecheck = ["npx tsc --noEmit"]
        profile.detected_by = "package.json"
        return profile

    if "pyproject.toml" in files:
        pyproject = _read_toml(workspace / "pyproject.toml")
        profile = ProjectProfile(language="python", package_manager="pip")
        dev_deps = " ".join(
            (pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", [])
             or pyproject.get("project", {}).get("dependencies", []))
        )
        profile.install = ["pip install -e .[dev]"] if dev_deps else ["pip install -e ."]
        profile.test = [_python_cmd("pytest")]
        if "[tool.ruff]" in pyproject or "ruff" in dev_deps:
            profile.lint = [_python_cmd("ruff") + " check ."]
        if "[tool.mypy]" in pyproject or "mypy" in dev_deps:
            profile.typecheck = [_python_cmd("mypy") + " ."]
        profile.detected_by = "pyproject.toml"
        return profile

    if "requirements.txt" in files:
        profile = ProjectProfile(
            language="python",
            package_manager="pip",
            install=["pip install -r requirements.txt"],
            test=[_python_cmd("pytest")],
            detected_by="requirements.txt",
        )
        return profile

    if "Cargo.toml" in files:
        return ProjectProfile(
            language="rust",
            package_manager="cargo",
            install=[],
            test=["cargo test"],
            build=["cargo check"],
            lint=["cargo clippy -- -D warnings"],
            detected_by="Cargo.toml",
        )

    if "go.mod" in files:
        return ProjectProfile(
            language="go",
            package_manager="go",
            install=[],
            test=["go test ./..."],
            lint=["go vet ./..."],
            detected_by="go.mod",
        )

    if "pom.xml" in files:
        return ProjectProfile(
            language="java",
            package_manager="maven",
            install=[],
            test=["mvn test"],
            build=["mvn package -DskipTests"],
            detected_by="pom.xml",
        )

    if "build.gradle" in files or "build.gradle.kts" in files:
        return ProjectProfile(
            language="java",
            package_manager="gradle",
            install=[],
            test=["gradle test"],
            build=["gradle build -x test"],
            detected_by="build.gradle",
        )

    if "composer.json" in files:
        composer = _read_json(workspace / "composer.json")
        scripts = composer.get("scripts", {})
        profile = ProjectProfile(language="php", package_manager="composer")
        profile.install = ["composer install"]
        if "test" in scripts:
            profile.test = ["composer test"]
        else:
            profile.test = ["vendor/bin/phpunit"]
        profile.detected_by = "composer.json"
        return profile

    if "pubspec.yaml" in files:
        return ProjectProfile(
            language="dart",
            package_manager="flutter",
            install=[],
            test=["flutter test"],
            lint=["flutter analyze"],
            detected_by="pubspec.yaml",
        )

    return ProjectProfile()


__all__ = ["ProjectProfile", "detect"]
