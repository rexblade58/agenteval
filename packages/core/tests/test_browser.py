"""Tests for the AgentEval browser verifier.

Run with: pytest packages/core/tests
"""

import sys
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.arena.browser import BrowserConfig, BrowserVerifier, _playwright_available  # noqa: E402


class TestBrowserConfig:
    def test_defaults(self):
        cfg = BrowserConfig.from_dict(None)
        assert cfg.enabled
        assert cfg.url == "http://localhost:3000"
        assert cfg.checks == []

    def test_from_dict(self):
        cfg = BrowserConfig.from_dict(
            {
                "start": "python server.py",
                "url": "http://localhost:8765",
                "checks": [{"navigate": "/checkout"}, {"expect_text": "Checkout"}],
                "ready_timeout_s": 30,
            }
        )
        assert cfg.start_command == "python server.py"
        assert cfg.url == "http://localhost:8765"
        assert len(cfg.checks) == 2

    def test_disabled(self):
        cfg = BrowserConfig.from_dict({"enabled": False})
        assert not cfg.enabled


class TestBrowserVerifier:
    def test_disabled_passes(self, tmp_path):
        cfg = BrowserConfig.from_dict({"enabled": False})
        result = BrowserVerifier(config=cfg).verify(tmp_path)
        assert result.passed
        assert "disabled" in (result.error or "")

    def test_skips_without_playwright(self, tmp_path):
        if _playwright_available():
            # playwright is installed here; simulate absence
            with mock.patch("agenteval.arena.browser._playwright_available", return_value=False):
                result = BrowserVerifier().verify(tmp_path)
        else:
            result = BrowserVerifier().verify(tmp_path)
        assert result.passed, "browser verification should skip, not fail, without playwright"
        assert "skipped" in (result.error or "")

    def test_real_flow_with_fixture_server(self, tmp_path):
        """End-to-end: start the fixture server, drive it with Playwright."""
        if not _playwright_available():
            import pytest

            pytest.skip("playwright not installed")

        cfg = BrowserConfig(
            start_command=f'python "{Path(__file__).resolve().parent / "fixtures" / "web_app" / "server.py"}"',
            url="http://127.0.0.1:8765",
            ready_timeout_s=20,
            checks=[
                {"navigate": "/checkout"},
                {"expect_text": "Checkout"},
                {"expect_text": "Total"},
            ],
        )
        result = BrowserVerifier(config=cfg).verify(tmp_path)
        assert result.passed, result.error
        assert result.total_commands == 3
        assert result.passed_commands == 3
        assert (tmp_path / "browser" / "final.png").exists()

    def test_failing_check(self, tmp_path):
        if not _playwright_available():
            import pytest

            pytest.skip("playwright not installed")

        cfg = BrowserConfig(
            start_command=f'python "{Path(__file__).resolve().parent / "fixtures" / "web_app" / "server.py"}"',
            url="http://127.0.0.1:8765",
            ready_timeout_s=20,
            checks=[{"navigate": "/checkout"}, {"expect_text": "THIS TEXT DOES NOT EXIST"}],
        )
        result = BrowserVerifier(config=cfg).verify(tmp_path)
        assert not result.passed
        assert result.passed_commands == 1
        assert result.total_commands == 2
