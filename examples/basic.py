"""Minimal example: evaluate the mock provider against the full suite."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "core"))

from agenteval.evaluator import Evaluator
from agenteval.providers import MockProvider
from agenteval.report import to_markdown


def main() -> None:
    provider = MockProvider()
    evaluator = Evaluator(provider, suite="all")
    report = evaluator.run_suite()
    print(to_markdown(report))


if __name__ == "__main__":
    main()
