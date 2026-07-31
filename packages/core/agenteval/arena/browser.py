"""AgentEval arena - browser verification via Playwright.

Starts the web application, opens it in a real browser, walks through the
configured checks (navigation, expected text, console errors, failed
network requests), and captures screenshots. Playwright is an optional
dependency - the verifier reports a clear skip result when unavailable.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .exec import ExecResult, run_command
from .project import ProjectProfile
from .verifiers import VerificationResult, Verifier

DEFAULT_URL = "http://localhost:3000"


@dataclass
class BrowserConfig:
    """Configuration for the browser verifier (browser: section of agenteval.yaml)."""

    enabled: bool = True
    start_command: str = "npm run dev"
    url: str = DEFAULT_URL
    ready_timeout_s: int = 60
    ready_text: str = ""  # optional text to wait for on the page
    checks: list[dict[str, Any]] = field(default_factory=list)
    screenshots_dir: str = "browser"
    video: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BrowserConfig":
        if not data:
            return cls()
        return cls(
            enabled=bool(data.get("enabled", True)),
            start_command=str(data.get("start", data.get("start_command", "npm run dev"))),
            url=str(data.get("url", DEFAULT_URL)),
            ready_timeout_s=int(data.get("ready_timeout_s", 60)),
            ready_text=str(data.get("ready_text", "")),
            checks=list(data.get("checks", []) or []),
            screenshots_dir=str(data.get("screenshots_dir", "browser")),
            video=bool(data.get("video", False)),
        )


class _ServerHandle:
    """A running app server process with safe process-tree cleanup."""

    def __init__(self, proc: subprocess.Popen, command: str):
        self.proc = proc
        self.command = command

    def kill(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                    capture_output=True, timeout=10,
                )
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            try:
                self.proc.kill()
            except OSError:
                pass


class BrowserVerifier(Verifier):
    """Starts the app and verifies it in a real browser with Playwright."""

    name = "browser"

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()

    def verify(self, workspace: Path, profile: ProjectProfile | None = None) -> VerificationResult:
        if not self.config.enabled:
            return VerificationResult(
                name=self.name, passed=True, error="browser verification disabled"
            )
        if not _playwright_available():
            return VerificationResult(
                name=self.name,
                passed=True,  # skip, not fail - browser verification is opt-in
                error="skipped: playwright is not installed (pip install playwright && playwright install chromium)",
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:  # pragma: no cover - defensive
            return VerificationResult(
                name=self.name, passed=False, error="playwright import failed"
            )

        # 1. Start the application (long-running server, not a blocking command)
        server = _start_server(workspace, self.config.start_command)
        if server is None:
            return VerificationResult(
                name=self.name, passed=False, error=f"app start failed: {self.config.start_command}"
            )

        try:
            # 2. Wait for readiness
            ready = _wait_ready(self.config.url, self.config.ready_timeout_s)
            if not ready:
                return VerificationResult(
                    name=self.name,
                    passed=False,
                    error=f"app did not become ready at {self.config.url} "
                          f"within {self.config.ready_timeout_s}s",
                )

            # 3. Drive the browser
            return self._run_checks(workspace)
        finally:
            server.kill()

    def _run_checks(self, workspace: Path) -> VerificationResult:
        from playwright.sync_api import sync_playwright

        console_errors: list[str] = []
        failed_requests: list[str] = []
        check_results: list[ExecResult] = []
        screenshots: list[str] = []

        shots_dir = workspace / self.config.screenshots_dir
        shots_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir=str(shots_dir) if self.config.video else None
            )
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(str(msg.text)) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: failed_requests.append(req.url))

            checks = self.config.checks or [{"navigate": "/"}]
            try:
                for idx, check in enumerate(checks):
                    result = self._run_check(page, check, shots_dir, idx)
                    check_results.append(result)
            finally:
                page.screenshot(path=str(shots_dir / "final.png"), full_page=False)
                screenshots.append(str(shots_dir / "final.png"))
                browser.close()

        passed = all(r.ok for r in check_results)
        if not passed:
            failed = [c for c in check_results if not c.ok]
            error = "; ".join(f"{c.command}: {c.error or 'exit ' + str(c.exit_code)}" for c in failed[:3])
        elif console_errors or failed_requests:
            passed = False
            error = (
                f"{len(console_errors)} console error(s), "
                f"{len(failed_requests)} failed request(s)"
            )
        else:
            error = None

        return VerificationResult(
            name=self.name,
            passed=passed,
            passed_commands=sum(1 for r in check_results if r.ok),
            total_commands=len(check_results),
            commands=check_results,
            error=error,
        )

    def _run_check(self, page: Any, check: dict[str, Any], shots_dir: Path, idx: int) -> ExecResult:
        """Execute one browser check: navigate / expect_text / click / wait."""
        start = time.perf_counter()
        try:
            if "navigate" in check:
                target = check["navigate"]
                if not target.startswith(("http://", "https://")):
                    target = f"{self.config.url}{target}"
                page.goto(target, wait_until="networkidle", timeout=30000)
            if "wait_for" in check:
                page.wait_for_selector(check["wait_for"], timeout=30000)
            if "click" in check:
                page.click(check["click"])
            if "expect_text" in check:
                page.wait_for_selector(f"text={check['expect_text']}", timeout=15000)
            if "screenshot" in check:
                page.screenshot(path=str(shots_dir / f"check-{idx}.png"))
            elapsed = (time.perf_counter() - start) * 1000
            return ExecResult(
                command=f"browser: {check}",
                exit_code=0,
                duration_s=elapsed / 1000,
                stdout=f"ok: {check}",
            )
        except Exception as exc:  # noqa: BLE001 - playwright raises rich errors
            elapsed = (time.perf_counter() - start) * 1000
            return ExecResult(
                command=f"browser: {check}",
                exit_code=1,
                duration_s=elapsed / 1000,
                error=str(exc)[:300],
            )


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def _start_server(workspace: Path, command: str) -> _ServerHandle | None:
    """Launch a long-running server. Returns None on immediate failure."""
    try:
        proc = subprocess.Popen(
            command,
            cwd=str(workspace),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=os.name != "nt",
        )
    except OSError:
        return None
    # Give it a moment to crash on a bad command
    time.sleep(1.5)
    if proc.poll() is not None:
        return None
    return _ServerHandle(proc, command)


def _wait_ready(url: str, timeout_s: int) -> bool:
    """Poll the URL until it responds or the timeout elapses."""
    import httpx

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code < 500:
                return True
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(1)
    return False


__all__ = ["BrowserConfig", "BrowserVerifier", "_playwright_available"]

