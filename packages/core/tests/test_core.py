"""Tests for AgentEval core.

Run with: pytest packages/core/tests
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.evaluator import Evaluator
from agenteval.providers import MockProvider, Message
from agenteval.report import to_json, to_markdown
from agenteval.tasks import get_tasks


def test_mock_provider_returns_response():
    provider = MockProvider()
    result = provider.complete([Message(role="user", content="hello")])
    assert result.text
    assert result.latency_ms >= 0


def test_mock_provider_detects_code_request():
    provider = MockProvider()
    result = provider.complete([Message(role="user", content="write a function please")])
    assert "def" in result.text


def test_task_check_contains():
    task = get_tasks("qa")[0]  # qa-capital, reference "Paris"
    assert task.check("The capital of France is Paris.")
    assert not task.check("The capital of France is Berlin.")


def test_evaluator_mock_all_suite():
    provider = MockProvider()
    eval_ = Evaluator(provider, suite="all")
    report = eval_.run_suite()
    assert report.total_tasks > 0
    assert 0 <= report.accuracy <= 1
    assert report.passed + report.failed == report.total_tasks


def test_evaluator_pass_at_k():
    provider = MockProvider()
    eval_ = Evaluator(provider, suite="qa", n_samples=2)
    report = eval_.run_suite()
    assert report.results
    assert all(r.attempts == 2 for r in report.results)


def test_report_json_serializable():
    provider = MockProvider()
    report = Evaluator(provider, suite="codegen").run_suite()
    parsed = json.loads(to_json(report))
    assert parsed["provider"] == "mock"
    assert "accuracy" in parsed
    assert "results" in parsed


def test_report_has_schema_and_timestamp():
    provider = MockProvider()
    report = Evaluator(provider, suite="codegen").run_suite()
    parsed = json.loads(to_json(report))
    assert parsed["schema_version"] == 1
    assert "generated_at" in parsed
    assert parsed["generated_at"].endswith("+00:00") or "Z" in parsed["generated_at"]


def test_report_markdown_has_tables():
    provider = MockProvider()
    report = Evaluator(provider, suite="codegen").run_suite()
    md = to_markdown(report)
    assert "# AgentEval Report" in md
    assert "| Task |" in md
    assert "accuracy" in md.lower() or "Accuracy" in md


def test_unknown_provider_raises():
    from agenteval.providers import create_provider

    try:
        create_provider("does-not-exist")
        assert False, "should have raised"
    except ValueError:
        pass


def test_unknown_suite_raises():
    from agenteval.tasks import get_tasks

    try:
        get_tasks("nope")
        assert False, "should have raised"
    except ValueError:
        pass
