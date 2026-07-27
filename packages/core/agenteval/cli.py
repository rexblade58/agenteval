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

from .evaluator import EvaluationReport, Evaluator
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
    run.add_argument("--suite", default="all", choices=sorted(TASK_REGISTRY) + ["traces"],
                     help="Task suite to run (default: all; traces for multi-step tool use)")
    run.add_argument("--n-samples", type=int, default=1, help="Samples per task (pass@k)")
    run.add_argument("--temperature", type=float, default=0.7, help="Sampling temperature")
    run.add_argument("--scoring", choices=["contains", "semantic"], default="contains",
                     help="Task scoring mode (default: contains)")
    run.add_argument("--format", choices=["json", "markdown"], default="markdown",
                     help="Output format")
    run.add_argument("--output", default=None, help="Write the report to a file")
    run.add_argument("--review", default=None, metavar="FILE",
                     help="Write failed tasks to a review queue for human judgment")

    review = sub.add_parser("review", help="Review failed tasks (human-in-the-loop)")
    review.add_argument("file", help="Review queue file written by `run --review`")
    review.add_argument("--apply", action="store_true",
                        help="Merge human judgments into a re-scored report (JSON to stdout)")
    review.add_argument("--interactive", action="store_true",
                        help="Judge each pending task in a prompt loop, then save")
    review.add_argument("--yes", action="store_true",
                        help="With --interactive: mark everything pass without prompting")

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

    # Trace suite: multi-step tool-call evaluation
    if args.suite == "traces":
        return _run_traces(provider, args)

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

    if args.review:
        from .review import write_review_queue

        written = write_review_queue(Path(args.review), report)
        if written:
            print(f"Review queue written to {args.review} ({written} failed task(s) to judge)")
            print("Run: agenteval review <file> --interactive  then  --apply")
        else:
            print(f"No failed tasks - no review queue written")

    # Exit non-zero if accuracy is below 50% (useful for CI)
    return 0 if report.accuracy >= 0.5 else 2


def _review(args: argparse.Namespace) -> int:
    from .review import apply_review, interactive_review, load_review_queue

    path = Path(args.file)

    if args.interactive:
        updated = interactive_review(path, yes=args.yes)
        print(f"Updated {updated} judgment(s) in {path}")
        return 0

    if args.apply:
        meta, entries = load_review_queue(path)
        if not meta:
            print("error: no meta header in review queue (was it written by `run --review`?)",
                  file=sys.stderr)
            return 1
        pending = [e for e in entries if e.status == "pending"]
        if pending:
            print(f"warning: {len(pending)} pending judgment(s) - run "
                  f"`agenteval review {args.file} --interactive` first", file=sys.stderr)
        result = apply_review(meta, entries)
        print(json.dumps(result, indent=2))
        return 0

    meta, entries = load_review_queue(path)
    pending = sum(1 for e in entries if e.status == "pending")
    print(f"Review queue: {path}")
    print(f"  tasks judged: {len(entries) - pending}/{len(entries)}")
    print(f"  pending: {pending}")
    print(f"  suite: {meta.get('suite', '?')}  provider: {meta.get('provider', '?')}")
    for e in entries:
        print(f"  [{e.status:7s}] {e.task_id} ({e.category})")
    print("\nNext: agenteval review <file> --interactive  then  --apply")
    return 0


def _run_traces(provider: Any, args: argparse.Namespace) -> int:
    """Run the trace suite and emit an EvaluationReport with trace metrics."""
    from .trace_suites import TRACE_REGISTRY  # noqa: F401 - registers scenarios
    from .traces import TraceEvaluator

    print(f"Running suite 'traces' against {provider.name}/{provider.model}...")
    evaluator = TraceEvaluator(provider)
    results = evaluator.run_suite()

    success_count = sum(1 for r in results if r.success)
    scenarios = len(results)
    success_rate = success_count / scenarios if scenarios else 0.0
    avg_validity = sum(r.tool_validity for r in results) / scenarios if scenarios else 0.0
    avg_efficiency = sum(r.efficiency for r in results) / scenarios if scenarios else 0.0

    trace_metrics = {
        "scenarios": scenarios,
        "success_count": success_count,
        "success_rate": round(success_rate, 4),
        "avg_tool_validity": round(avg_validity, 4),
        "avg_efficiency": round(avg_efficiency, 4),
        "results": [
            {
                "trace_id": r.trace_id,
                "success": r.success,
                "steps": r.steps,
                "max_steps": r.max_steps,
                "tool_calls_total": r.tool_calls_total,
                "tool_calls_valid": r.tool_calls_valid,
                "tool_validity": round(r.tool_validity, 4),
                "efficiency": round(r.efficiency, 4),
                "error": r.error,
            }
            for r in results
        ],
    }

    report = EvaluationReport(
        provider=provider.name,
        model=provider.model,
        suite="traces",
        total_tasks=scenarios,
        passed=success_count,
        accuracy=success_rate,
        avg_latency_ms=0.0,
        total_cost_usd=0.0,
        trace_metrics=trace_metrics,
    )

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

    return 0 if success_rate >= 0.5 else 2


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
    try:
        from .trace_suites import TRACE_REGISTRY  # noqa: F401 - populates registry
        for name in sorted(TRACE_REGISTRY):
            print(f"  {name} ({len(TRACE_REGISTRY[name])} traces)")
    except ImportError:
        pass
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
    if args.command == "review":
        return _review(args)
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
