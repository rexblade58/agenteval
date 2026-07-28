"""AgentEval arena - safe subprocess execution helpers.

Cross-platform process runner used by agents, verifiers, and the worktree
manager. Enforces timeouts, caps captured output, and kills the whole
process tree on timeout.
"""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

MAX_OUTPUT_BYTES = 512 * 1024  # cap captured stdout/stderr per command


@dataclass
class ExecResult:
    """Outcome of one executed command."""

    command: str
    exit_code: int | None
    duration_s: float
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _cap(data: bytes) -> str:
    if len(data) > MAX_OUTPUT_BYTES:
        return data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace") + "\n...[truncated]"
    return data.decode("utf-8", errors="replace")


def _kill_tree(proc: subprocess.Popen) -> None:
    """Terminate the process and its children, cross-platform."""
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, timeout=10,
            )
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
        except OSError:
            pass


def run_command(
    command: list[str],
    cwd: Path,
    timeout_s: float,
    env: dict[str, str] | None = None,
    shell: bool = False,
) -> ExecResult:
    """Run a command with a hard timeout and bounded output capture."""
    display = " ".join(shlex.quote(c) for c in command) if not shell else command[0]
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    start = time.perf_counter()
    try:
        proc = subprocess.Popen(
            command if not shell else command[0],
            cwd=str(cwd),
            env=merged_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=shell,
            start_new_session=os.name != "nt",
        )
    except FileNotFoundError:
        return ExecResult(
            command=display,
            exit_code=None,
            duration_s=0.0,
            error=f"command not found: {command[0]}",
        )
    except OSError as exc:
        return ExecResult(
            command=display,
            exit_code=None,
            duration_s=0.0,
            error=str(exc),
        )

    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        stdout, stderr = proc.communicate()
    except Exception as exc:  # noqa: BLE001
        _kill_tree(proc)
        stdout, stderr = b"", b""
        elapsed = time.perf_counter() - start
        return ExecResult(
            command=display,
            exit_code=None,
            duration_s=elapsed,
            error=str(exc),
        )

    elapsed = time.perf_counter() - start
    return ExecResult(
        command=display,
        exit_code=proc.returncode,
        duration_s=elapsed,
        stdout=_cap(stdout),
        stderr=_cap(stderr),
        timed_out=timed_out,
    )


__all__ = ["ExecResult", "run_command"]
