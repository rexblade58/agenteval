"""Tests for the AgentEval dashboard.

Run with: pytest packages/core/tests
"""

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agenteval.dashboard import load_reports, make_handler, render_html


def _write_report(directory: Path, name: str, provider: str, accuracy: float,
                  generated_at: str) -> None:
    data = {
        "schema_version": 1,
        "generated_at": generated_at,
        "provider": provider,
        "model": "test-model",
        "suite": "codegen",
        "total_tasks": 4,
        "passed": int(accuracy * 4),
        "failed": 4 - int(accuracy * 4),
        "accuracy": accuracy,
        "avg_latency_ms": 123.4,
        "total_cost_usd": 0.001,
    }
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


def test_load_reports_filters_and_sorts(tmp_path):
    _write_report(tmp_path, "a.json", "openai", 0.8, "2026-07-01T00:00:00+00:00")
    _write_report(tmp_path, "b.json", "anthropic", 0.6, "2026-07-05T00:00:00+00:00")
    (tmp_path / "broken.json").write_text("not json", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    reports = load_reports(tmp_path)
    assert len(reports) == 2
    assert reports[0]["provider"] == "anthropic"  # newest first
    assert reports[1]["provider"] == "openai"
    assert "_file" in reports[0]


def test_load_reports_missing_dir(tmp_path):
    assert load_reports(tmp_path / "nope") == []


def test_render_html_contains_summary():
    reports_dir = Path(__file__).resolve().parent.parent / ".." / ".." / ".." / "examples" / "reports"
    reports = load_reports(reports_dir)
    html = render_html(reports)
    assert "AgentEval Dashboard" in html
    assert "Accuracy by provider" in html
    assert "All reports" in html
    if reports:
        assert reports[0]["_file"] in html


def test_dashboard_http_endpoints(tmp_path):
    _write_report(tmp_path, "a.json", "openai", 0.8, "2026-07-01T00:00:00+00:00")

    handler = make_handler(tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        base = f"http://127.0.0.1:{port}"
        with urllib.request.urlopen(f"{base}/") as resp:
            assert resp.status == 200
            assert "AgentEval Dashboard" in resp.read().decode("utf-8")

        with urllib.request.urlopen(f"{base}/api/reports") as resp:
            assert resp.status == 200
            body = json.loads(resp.read().decode("utf-8"))
            assert len(body) == 1
            assert body[0]["provider"] == "openai"

        with urllib.request.urlopen(f"{base}/reports/a.json") as resp:
            assert resp.status == 200
            assert json.loads(resp.read().decode("utf-8"))["provider"] == "openai"

        try:
            urllib.request.urlopen(f"{base}/reports/../secret.json")
            assert False, "path traversal should be rejected"
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)
