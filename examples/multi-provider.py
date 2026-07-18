"""Evaluate a real provider (OpenAI-compatible) against a suite.

Requires OPENAI_API_KEY in the environment, or pass api_key=.

    python examples/multi-provider.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "core"))

from agenteval.evaluator import Evaluator
from agenteval.providers import create_provider
from agenteval.report import to_json


def main() -> None:
    # Swap "openai" for "anthropic" or "ollama" to try other providers
    provider = create_provider("openai", model="gpt-4o-mini")
    evaluator = Evaluator(provider, suite="qa", n_samples=1)
    report = evaluator.run_suite()
    print(to_json(report))


if __name__ == "__main__":
    main()
