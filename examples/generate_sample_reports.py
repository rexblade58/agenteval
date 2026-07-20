"""Generate sample evaluation reports for the examples/reports/ directory.

These reports demonstrate the JSON schema used by the CLI (--format json)
and give the future web dashboard (issue #4) realistic data to visualize.

Run from the repo root:

    python examples/generate_sample_reports.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "core"))

from agenteval.evaluator import Evaluator
from agenteval.providers import MockProvider
from agenteval.report import to_dict


def _timestamp(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _write(name: str, report: dict, days_ago: int) -> Path:
    report["generated_at"] = _timestamp(days_ago)
    out = Path(__file__).resolve().parent / "reports" / name
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def main() -> None:
    provider = MockProvider()
    reports_dir = Path(__file__).resolve().parent / "reports"
    reports_dir.mkdir(exist_ok=True)

    # Mock provider: perfect deterministic pass rate, zero cost
    report = Evaluator(provider, suite="all").run_suite()
    _write("mock-all.json", to_dict(report), days_ago=6)

    # Simulated OpenAI run at 3 provider qualities using the mock responses
    # with degraded latency/cost to approximate real-world numbers.
    baseline = to_dict(Evaluator(provider, suite="codegen").run_suite())
    baseline["provider"] = "openai"
    baseline["model"] = "gpt-4o-mini"
    baseline["avg_latency_ms"] = 420.0
    baseline["total_cost_usd"] = 0.000412
    for r in baseline["results"]:
        r["latency_ms"] = round(r["latency_ms"] * 420, 2)
    _write("openai-gpt-4o-mini-codegen.json", baseline, days_ago=5)

    older = json.loads(json.dumps(baseline))
    older["avg_latency_ms"] = 380.0
    older["total_cost_usd"] = 0.000391
    for r in older["results"]:
        r["latency_ms"] = round(r["latency_ms"] * 0.9, 2)
    _write("openai-gpt-4o-mini-codegen-old.json", older, days_ago=18)

    print(f"Sample reports written to {reports_dir}")


if __name__ == "__main__":
    main()
