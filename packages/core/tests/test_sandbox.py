"""Tests for the AgentEval Docker sandbox.

Run with: pytest packages/core/tests
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.agents import CommandAgent, AgentStatus  # noqa: E402
from agenteval.arena.sandbox import DockerSandbox, SandboxConfig  # noqa: E402


class TestSandboxConfig:
    def test_defaults(self):
        cfg = SandboxConfig.from_dict(None)
        assert cfg.image == "python:3.11-slim"
        assert cfg.network == "bridge"
        assert cfg.cpus is None

    def test_from_dict(self):
        cfg = SandboxConfig.from_dict(
            {"image": "node:20", "network": "none", "cpus": "2", "memory": "2g", "pids_limit": 256}
        )
        assert cfg.image == "node:20"
        assert cfg.network == "none"
        assert cfg.cpus == "2"
        assert cfg.memory == "2g"
        assert cfg.pids_limit == 256


class TestDockerSandbox:
    def test_wrap_command(self, tmp_path):
        sandbox = DockerSandbox()
        cmd = sandbox.wrap_command(["codex", "exec", "task"], tmp_path, "agenteval-codex-123")
        joined = " ".join(cmd)
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "--rm" in cmd
        assert "--network" in cmd
        assert "--volume" in cmd
        assert str(tmp_path.resolve()).replace("\\", "/") in joined.replace("\\", "/")
        assert "--workdir" in cmd
        assert cmd[-1] == "task"  # the original command is appended after the image
        assert "codex" in cmd

    def test_wrap_shell(self, tmp_path):
        sandbox = DockerSandbox()
        cmd = sandbox.wrap_shell("npm test", tmp_path, "agenteval-tests-1")
        assert cmd[-3:] == ["sh", "-c", "npm test"]

    def test_wrap_network_none(self, tmp_path):
        sandbox = DockerSandbox(SandboxConfig.from_dict({"network": "none"}))
        cmd = sandbox.wrap_command(["true"], tmp_path, "n")
        assert "--network" in cmd
        assert cmd[cmd.index("--network") + 1] == "none"

    def test_wrap_resource_limits(self, tmp_path):
        sandbox = DockerSandbox(
            SandboxConfig.from_dict({"cpus": "2", "memory": "2g", "pids_limit": 256})
        )
        cmd = sandbox.wrap_command(["true"], tmp_path, "n")
        joined = " ".join(cmd)
        assert "--cpus 2" in joined
        assert "--memory 2g" in joined
        assert "--pids-limit 256" in joined

    def test_available_returns_bool(self):
        assert isinstance(DockerSandbox.available(), bool)


class TestSandboxedAgent:
    def test_agent_runs_through_sandbox(self, tmp_path):
        sandbox = DockerSandbox()
        agent = CommandAgent(
            command="codex exec {task}",
            name="codex",
            timeout_s=60,
            sandbox=sandbox,
        )

        fake = mock.Mock()
        fake.error = None
        fake.timed_out = False
        fake.exit_code = 0
        fake.duration_s = 1.0
        fake.stdout = "done"
        fake.stderr = ""
        fake.command = "docker run ..."

        with mock.patch("agenteval.arena.sandbox.run_command", return_value=fake) as run:
            result = agent.run(tmp_path, "fix the bug")

        assert result.status == AgentStatus.PASS
        run.assert_called_once()  # sandbox.run delegated to the sandbox's run_command

    def test_agent_without_sandbox_uses_run_command(self, tmp_path):
        agent = CommandAgent(command="codex exec {task}", name="codex", timeout_s=60)

        fake = mock.Mock()
        fake.error = None
        fake.timed_out = False
        fake.exit_code = 0
        fake.duration_s = 1.0
        fake.stdout = "done"
        fake.stderr = ""
        fake.command = "codex exec task"

        with mock.patch("agenteval.arena.agents.run_command", return_value=fake) as run:
            result = agent.run(tmp_path, "fix the bug")

        assert result.status == AgentStatus.PASS
        run.assert_called_once()
