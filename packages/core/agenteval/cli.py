"""AgentEval - command line interface.

Usage:
  agenteval run --provider openai --model gpt-4o-mini --suite all
  agenteval run --provider mock --suite codegen
  agenteval serve --dir reports
  agenteval arena --repo . --task "fix the failing checkout test" --agents codex,claude
  agenteval agents list
  agenteval verifiers list
  agenteval doctor
  agenteval list-providers
  agenteval list-suites
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows consoles default to cp1252 and choke on emoji in reports
if sys.stdout and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

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

    arena = sub.add_parser("arena", help="Battle coding agents against a real task in isolated workspaces")
    arena.add_argument("--repo", default=".", help="Local repo path or git URL (default: .)")
    arena.add_argument("--task", default="", help="Task description (or path to a task .md/.yaml file)")
    arena.add_argument("--agents", default="", help="Comma-separated agent names (codex,claude,opencode,...)")
    arena.add_argument("--runs", type=int, default=1, help="Attempts per agent (default: 1)")
    arena.add_argument("--parallel", action="store_true", help="Run agents concurrently")
    arena.add_argument("--timeout", type=int, default=900, help="Per-agent timeout in seconds (default: 900)")
    arena.add_argument("--commit", default=None, help="Starting commit (default: HEAD)")
    arena.add_argument("--verifiers", default="", help="Comma-separated verifiers (tests,build,lint,typecheck)")
    arena.add_argument("--format", choices=["json", "markdown", "html"], default="markdown",
                       help="Report format (default: markdown)")
    arena.add_argument("--output-dir", default=None, help="Directory for report artifacts (default: .agenteval/runs/<timestamp>)")
    arena.add_argument("--keep-worktrees", action="store_true", help="Do not remove worktrees after the run")
    arena.add_argument("--create-pr", action="store_true",
                       help="Push the winner's solution as a branch and open a PR (requires GH_TOKEN)")
    arena.add_argument("--sandbox", choices=["none", "docker"], default=None,
                       help="Run agents and verification inside a Docker sandbox (default: none)")
    arena.add_argument("--badge", default=None, metavar="FILE",
                       help="Write a winner badge SVG after the run")

    agents_sub = sub.add_parser("agents", help="List available agent adapters")
    agents_sub.add_argument("list", nargs="?", default="list", help="Subcommand (only 'list')")

    verifiers_sub = sub.add_parser("verifiers", help="List available verifiers")
    verifiers_sub.add_argument("list", nargs="?", default="list", help="Subcommand (only 'list')")

    issue = sub.add_parser("issue", help="Turn a GitHub issue into an arena battle")
    issue.add_argument("url", help="GitHub issue URL (https://github.com/<owner>/<repo>/issues/<n>)")
    issue.add_argument("--agents", default="", help="Comma-separated agent names")
    issue.add_argument("--runs", type=int, default=1, help="Attempts per agent")
    issue.add_argument("--parallel", action="store_true", help="Run agents concurrently")
    issue.add_argument("--timeout", type=int, default=900, help="Per-agent timeout in seconds")
    issue.add_argument("--format", choices=["json", "markdown", "html"], default="markdown",
                       help="Report format (default: markdown)")
    issue.add_argument("--output-dir", default=None, help="Artifact directory")
    issue.add_argument("--github-comment", action="store_true",
                       help="Post the result back as a comment on the issue")
    issue.add_argument("--create-pr", action="store_true",
                       help="Push the winner's solution as a branch and open a PR (requires GH_TOKEN)")
    issue.add_argument("--sandbox", choices=["none", "docker"], default=None,
                       help="Run agents and verification inside a Docker sandbox (default: none)")

    sub.add_parser("doctor", help="Check environment readiness for arena evaluation")

    verify = sub.add_parser("verify", help="Run tests/build/lint/typecheck in place and report a summary")
    verify.add_argument("--repo", default=".", help="Repository path (default: .)")
    verify.add_argument("--timeout", type=int, default=900, help="Per-command timeout in seconds")
    verify.add_argument("--badge", default=None, metavar="FILE",
                        help="Write an SVG badge (agenteval-verified.svg)")

    benchmark = sub.add_parser("benchmark", help="Manage community benchmark packs")
    benchmark.add_argument("subcommand", choices=["list", "install", "run"])
    benchmark.add_argument("name", nargs="?", default=None,
                           help="Pack name (list/run) or source (install: git URL or directory)")
    benchmark.add_argument("--agents", default="", help="Override agents (comma-separated)")
    benchmark.add_argument("--dir", default="benchmarks",
                           help="Pack directory (default: benchmarks)")
    benchmark.add_argument("--timeout", type=int, default=None, help="Override per-task timeout")

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


def _verify(args: argparse.Namespace) -> int:
    from .arena.verify import all_passed, summary, verify_project
    from .arena.badges import markdown_snippet, verified_badge, write_badge

    workspace = Path(args.repo)
    if not workspace.is_dir():
        print(f"error: not a directory: {workspace}", file=sys.stderr)
        return 1

    print(f"Verifying {workspace} ...\n")
    results = verify_project(workspace, timeout_s=args.timeout)
    print(summary(results))

    if args.badge:
        passed = all_passed(results)
        svg = verified_badge(passed)
        write_badge(svg, Path(args.badge))
        print(f"\nBadge written to {args.badge}")
        print(f"README snippet: {markdown_snippet(args.badge)}")

    return 0 if all_passed(results) else 2


def _benchmark(args: argparse.Namespace) -> int:
    from .arena.benchmarks import (
        BenchmarkError,
        discover_packs,
        install_pack,
    )

    packs_dir = Path(args.dir)

    if args.subcommand == "list":
        packs = discover_packs(packs_dir)
        if not packs:
            print(f"No benchmark packs found in {packs_dir} "
                  f"(run 'agenteval benchmark install <git-url|dir>' to add one)")
            return 0
        print(f"Benchmark packs in {packs_dir}:\n")
        for pack in packs:
            agents = ", ".join(pack.agents) if pack.agents else "all installed"
            print(f"  {pack.name:<24} {pack.description}")
            print(f"    repo: {pack.repo}  tasks: {len(pack.tasks)}  agents: {agents}")
        return 0

    if args.subcommand == "install":
        if not args.name:
            print("error: benchmark install requires a source (git URL or directory)", file=sys.stderr)
            return 1
        try:
            target = install_pack(args.name, packs_dir)
        except BenchmarkError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"Installed benchmark pack at {target}")
        return 0

    # run
    if not args.name:
        print("error: benchmark run requires a pack name", file=sys.stderr)
        return 1
    pack = next(
        (p for p in discover_packs(packs_dir) if p.name == args.name),
        None,
    )
    if pack is None:
        print(f"error: no benchmark pack named '{args.name}' in {packs_dir}", file=sys.stderr)
        return 1

    if not pack.tasks:
        print(f"error: pack '{pack.name}' has no tasks", file=sys.stderr)
        return 1
    agents = [a.strip() for a in args.agents.split(",") if a.strip()] or pack.agents
    if not agents:
        print(f"error: pack '{pack.name}' defines no agents - pass --agents codex,claude",
              file=sys.stderr)
        return 1

    from .arena.arena import ArenaConfig, ArenaRunner
    from .arena.config import load_agent_configs, load_browser_config, load_sandbox_config

    # Resolve relative repo paths against the pack's own directory
    pack_dir = Path(pack.source)
    repo_target = pack.repo
    if not pack.repo.startswith(("https://", "http://", "git@", "ssh://", "git://")):
        candidate = Path(pack.repo)
        if not candidate.is_absolute():
            candidate = pack_dir / pack.repo
        repo_target = str(candidate)

    print(f"Benchmark: {pack.name}")
    print(f"  {pack.description}")
    print(f"  repo:    {repo_target}")
    print(f"  tasks:   {len(pack.tasks)}")
    print(f"  agents:  {', '.join(agents)}\n")

    failures = 0
    for idx, task in enumerate(pack.tasks, 1):
        print(f"[{idx}/{len(pack.tasks)}] {task[:90]}")
        config = ArenaConfig(
            repo=repo_target,
            task=task,
            agents=agents,
            runs=pack.runs,
            parallel=pack.parallel,
            timeout_s=args.timeout or pack.timeout,
            commit=pack.commit,
        )
        if repo_target.startswith(("https://", "http://", "git@", "ssh://", "git://")):
            cwd = Path.cwd()
            config.agent_configs = load_agent_configs(cwd)
            config.browser_config = load_browser_config(cwd)
            config.sandbox_config = load_sandbox_config(cwd)
        else:
            repo_path = Path(repo_target)
            config.agent_configs = load_agent_configs(pack_dir)
            config.browser_config = load_browser_config(pack_dir)
            config.sandbox_config = load_sandbox_config(pack_dir)

        runner = ArenaRunner(config)
        try:
            result = runner.run()
        except RuntimeError as exc:
            print(f"  error: {exc}", file=sys.stderr)
            failures += 1
            continue

        winner = result.winner
        summary = f"{winner.agent} ({winner.score.total})" if winner else "no winner"
        print(f"  -> {summary}\n")
        if winner is None or winner.score.total < 60:
            failures += 1

    print(f"Benchmark complete: {len(pack.tasks) - failures}/{len(pack.tasks)} task(s) passed")
    return 0 if failures == 0 else 2


def _run_arena(args: argparse.Namespace) -> int:
    repo = Path(args.repo)
    task_text, task_file = _load_task(args.task, repo)
    return _execute_arena(
        repo=repo,
        task_text=task_text,
        task_file=task_file,
        agents=[a.strip() for a in args.agents.split(",") if a.strip()],
        runs=args.runs,
        parallel=args.parallel,
        timeout_s=args.timeout,
        commit=args.commit,
        verifiers=[v.strip() for v in args.verifiers.split(",") if v.strip()],
        keep_worktrees=args.keep_worktrees,
        fmt=args.format,
        output_dir=args.output_dir,
        create_pr=args.create_pr,
        sandbox=args.sandbox,
        badge_path=args.badge,
    )


def _run_issue(args: argparse.Namespace) -> int:
    from .arena.issues import IssueError, fetch_issue

    print(f"Fetching issue {args.url} ...")
    try:
        issue = fetch_issue(args.url)
    except IssueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"  #{issue.number} {issue.title}  ({issue.state})")
    if issue.state == "closed":
        print("warning: issue is closed; task may still be valid", file=sys.stderr)

    task_text = issue.task_text
    code = _execute_arena(
        repo=issue.clone_url,
        task_text=task_text,
        task_file=None,
        agents=[a.strip() for a in args.agents.split(",") if a.strip()],
        runs=args.runs,
        parallel=args.parallel,
        timeout_s=args.timeout,
        commit=None,
        verifiers=[],
        keep_worktrees=False,
        fmt=args.format,
        output_dir=args.output_dir,
        github_comment=(issue, task_text) if args.github_comment else None,
        create_pr=args.create_pr,
        sandbox=args.sandbox,
    )
    return code


def _execute_arena(
    repo: Path | str,
    task_text: str,
    task_file: Path | None,
    agents: list[str],
    runs: int,
    parallel: bool,
    timeout_s: int,
    commit: str | None,
    verifiers: list[str],
    keep_worktrees: bool,
    fmt: str,
    output_dir: str | None,
    github_comment: tuple[Any, str] | None = None,
    create_pr: bool = False,
    sandbox: str | None = None,
    badge_path: str | None = None,
) -> int:
    from .arena.arena import ArenaRunner
    from .arena.config import (
        load_agent_configs,
        load_browser_config,
        load_profile_override,
        load_sandbox_config,
        load_verify_commands,
        load_weights,
        config_from_repo,
    )
    from .arena.results import write_artifacts

    repo_path = Path(repo) if not _is_url(repo) else None
    config = config_from_repo(
        repo_path or Path("."),
        {
            "repo": str(repo),
            "task": task_text,
            "task_file": task_file,
            "agents": agents,
            "runs": runs,
            "parallel": parallel,
            "timeout_s": timeout_s,
            "commit": commit,
            "verifiers": verifiers,
            "keep_worktrees": keep_worktrees,
            "create_pr": create_pr,
        },
    )
    if repo_path is not None:
        config.agent_configs = load_agent_configs(repo_path)
        config.verify_commands = load_verify_commands(repo_path)
        config.weights = load_weights(repo_path)
        config.profile = load_profile_override(repo_path)
        config.browser_config = load_browser_config(repo_path)
        config.sandbox_config = load_sandbox_config(repo_path)
    else:
        # Remote repos: read custom agents/config from the current directory
        cwd = Path.cwd()
        config.agent_configs = load_agent_configs(cwd)
        config.verify_commands = load_verify_commands(cwd)
        config.weights = load_weights(cwd)
        config.profile = load_profile_override(cwd)
        config.browser_config = load_browser_config(cwd)
        config.sandbox_config = load_sandbox_config(cwd)
    if sandbox is not None:
        config.sandbox = sandbox
    config.quiet = fmt == "json"

    # Browser verification is opt-in via config (avoids surprising Playwright installs)
    if config.browser_config and "browser" not in config.verifiers:
        config.verifiers = list(config.verifiers) + ["browser"]

    if not config.task:
        print("error: a task is required (--task \"...\" or a task file)", file=sys.stderr)
        return 1
    if not config.agents:
        print("error: at least one agent is required (--agents codex,claude,...)", file=sys.stderr)
        return 1

    runner = ArenaRunner(config)
    try:
        result = runner.run()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    run_dir = output_dir
    if run_dir is None:
        from datetime import datetime, timezone

        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
        run_dir = str(Path(".agenteval") / "runs" / stamp)
    paths = write_artifacts(result, Path(run_dir))

    if fmt == "json":
        print(result.to_json())
    elif fmt == "html":
        print(result.to_html())
    else:
        print(result.to_markdown())

    if github_comment:
        issue, task_text_from_issue = github_comment
        from .arena.github import ReportError, build_comment, post_issue_comment

        try:
            comment = build_comment(result)
            url = post_issue_comment(issue.owner, issue.repo, issue.number, comment)
            print(f"Result posted: {url}", file=sys.stderr)
        except ReportError as exc:
            print(f"warning: could not post comment: {exc}", file=sys.stderr)

    print(f"\nArtifacts: {paths['json'].parent}", file=sys.stderr)

    if badge_path:
        from .arena.badges import markdown_snippet, winner_badge, write_badge

        write_badge(winner_badge(result), Path(badge_path))
        print(f"Winner badge written to {badge_path}")
        print(f"README snippet: {markdown_snippet(badge_path)}", file=sys.stderr)

    return 0


def _is_url(value: str | Path) -> bool:
    return str(value).startswith(("https://", "http://", "git@", "ssh://", "git://"))


def _load_task(task: str, repo: Path) -> tuple[str, Path | None]:
    """Resolve --task: inline text or a task file (markdown/yaml)."""
    if not task:
        return "", None
    candidate = Path(task)
    if not candidate.is_file():
        candidate = repo / task
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip(), candidate
    return task, None


def _agents_list() -> int:
    from .arena.agents import list_agents

    print("Available agent adapters:")
    for info in list_agents():
        marker = " (not installed)" if not _agent_installed(info["name"]) else ""
        print(f"  {info['name']:<12} {info['display_name']:<16} {info['description']}{marker}")
    return 0


def _agent_installed(name: str) -> bool:
    if name == "command":
        return True
    from .arena.agents import AGENT_REGISTRY

    cls = AGENT_REGISTRY.get(name)
    if cls is None:
        return False
    try:
        return cls().available()
    except Exception:  # noqa: BLE001
        return False


def _verifiers_list() -> int:
    from .arena.verifiers import list_verifiers

    print("Available verifiers:")
    for info in list_verifiers():
        print(f"  {info['name']:<12} {info['verifier']}")
    return 0


def _doctor() -> int:
    from .arena.doctor import critical_ok, run_doctor

    checks = run_doctor()
    print("AgentEval Doctor\n")
    for check in checks:
        symbol = "✓" if check.ok else "✗"
        detail = f"  {check.detail}" if check.detail else ""
        print(f"{symbol} {check.name}{detail}")
    print("\nReady for arena evaluation." if critical_ok(checks)
          else "\nMissing required tooling: install git and Python first.")
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
    if args.command == "arena":
        return _run_arena(args)
    if args.command == "issue":
        return _run_issue(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "benchmark":
        return _benchmark(args)
    if args.command == "agents":
        return _agents_list()
    if args.command == "verifiers":
        return _verifiers_list()
    if args.command == "doctor":
        return _doctor()
    if args.command == "list-providers":
        return _list_providers()
    if args.command == "list-suites":
        return _list_suites()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
