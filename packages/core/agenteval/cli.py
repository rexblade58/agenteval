"""AgentEval - command line interface.

Usage:
  agenteval run --provider openai --model gpt-4o-mini --suite all
  agenteval run --provider mock --suite codegen
  agenteval serve --dir reports
  agenteval list-providers
  agenteval list-suites
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import Evaluator
from .providers import PROVIDER_REGISTRY, create_provider
from .report import to_json, to_markdown
from .tasks import TASK_REGISTRY


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agenteval",
        description="Evaluate any AI agent across providers with standardized benchmarks.",
    )
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run an evaluation suite")
    run.add_argument("--provider", default="mock", choices=sorted(PROVIDER_REGISTRY),
                     help="LLM provider (default: mock)")
    run.add_argument("--model", default=None, help="Model identifier")
    run.add_argument("--suite", default="all", choices=sorted(TASK_REGISTRY),
                     help="Task suite to run (default: all)")
    run.add_argument("--n-samples", type=int, default=1, help="Samples per task (pass@k)")
    run.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    run.add_argument("--scoring", choices=["contains", "semantic"], default="contains",
                     help="Task scoring mode (default: contains)")
    run.add_argument("--format", choices=["json", "markdown"], default="markdown",
                     help="Output format")
    run.add_argument("--output", default=None, help="Write the report to a file")

    serve = sub.add_parser("serve", help="Start the local web dashboard")
    serve.add_argument("--dir", default="reports",
                       help="Directory of evaluation reports (default: reports)")
    serve.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    sub.add_parser("list-providers", help="List available providers")
    sub.add_parser("list-suites", help="List available task suites")

    return parser


def _run(args: argparse.Namespace) -> int:
    kwargs = {}
    if args.model:
        kwargs["model"] = args.model
    try:
        provider = create_provider(args.provider, **kwargs)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    evaluator = Evaluator(provider, suite=args.suite, n_samples=args.n_samples,
                          temperature=args.temperature, scoring=args.scoring)
    print(f"Running suite '{args.suite}' against {args.provider}/{provider.model}...")
    report = evaluator.run_suite()

    if args.format == "json":
        text = to_json(report)
    else:
        text = to_markdown(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Report written to {args.output}")
    else:
        print(text)

    # Exit non-zero if accuracy is below 50% (useful for CI)
    return 0 if report.accuracy >= 0.5 else 2


def _list_providers() -> int:
    print("Available providers:")
    for name in sorted(PROVIDER_REGISTRY):
        print(f"  {name}")
    return 0


def _list_suites() -> int:
    print("Available task suites:")
    for name in sorted(TASK_REGISTRY):
        tasks = TASK_REGISTRY[name]
        print(f"  {name} ({len(tasks)} tasks)")
    return 0


def _serve(args: argparse.Namespace) -> int:
    from .dashboard import serve as serve_dashboard

    serve_dashboard(Path(args.dir), host=args.host, port=args.port)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return _run(args)
    if args.command == "serve":
        return _serve(args)
    if args.command == "list-providers":
        return _list_providers()
    if args.command == "list-suites":
        return _list_suites()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
