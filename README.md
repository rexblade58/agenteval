<div align="center">

# 🤖 AgentEval

**Make AI agents prove their code works.**

AgentEval runs coding agents against the same real software task, executes
their patches in isolated repositories, verifies the results with real
tests, and tells you which agent actually performed best.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](packages/core/pyproject.toml)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-blue.svg)](packages/sdk-ts/package.json)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

## Why AgentEval?

Every team adopting AI coding agents needs one answer:

> **Which agent actually fixed the bug?**

Most "agent comparisons" are vibes: who *looks* like they did better. AgentEval
replaces opinions with evidence — each agent works on the exact same task in
its own isolated copy of the repository, and the results are verified with
real test/build/lint commands, not LLM judges.

```bash
agenteval arena \
  --repo . \
  --task "fix checkout discount calculation" \
  --agents codex,claude,opencode
```

```text
Agent        Tests    Build   Regression   Cost     Time    Score
─────────────────────────────────────────────────────────────────
Codex        47/47    PASS    0            $0.31    4m12s   96
Claude       47/47    PASS    1            $0.48    3m51s   92
OpenCode     39/42    FAIL    3            $0.08    5m03s   71

🏆 Winner: Codex
```

---

## Quick start

```bash
pip install -e packages/core

# check your environment
agenteval doctor

# battle installed coding agents on the current repo
agenteval arena \
  --repo . \
  --task "fix the failing checkout test" \
  --agents codex,claude
```

No coding agents installed? The generic `command` adapter runs any
executable, and custom agents are one YAML block away:

```yaml
# agenteval.yaml
agents:
  my-agent:
    command: my-agent run "{task}"
    timeout: 900
```

See [Arena docs](docs/arena.md) for agents, verification, scoring, and
results.

---

## Two workflows

### 🏟️ AgentEval Arena — coding agents

| Capability | Status |
| :--- | :--- |
| Agent abstraction (codex, claude, gemini, opencode, aider, command) | ✅ |
| Isolated git worktrees (same starting commit per agent) | ✅ |
| Remote repository support (cloned, never modified) | ✅ |
| Automatic project detection (Node, Python, Rust, Go, Java, PHP, Flutter) | ✅ |
| Real verification: tests, build, lint, typecheck | ✅ |
| Baseline regression detection (tests fixed vs new failures) | ✅ |
| Transparent weighted scoring (functional 50% > regression 20% > ...) | ✅ |
| Parallel agent execution | ✅ |
| Result states: PASS / PARTIAL / FAIL / TIMEOUT / AGENT_ERROR / ... | ✅ |
| JSON / Markdown / HTML reports with full reproducibility metadata | ✅ |
| `agenteval.yaml` configuration | ✅ |
| `agenteval doctor` environment check | ✅ |
| GitHub issue mode (`agenteval issue <url>`) | ✅ |
| GitHub comment reporting (`--github-comment`) | ✅ |
| Winning-solution PR creation (`--create-pr`) | ✅ |
| Browser verification (Playwright, opt-in) | ✅ |
| Docker sandbox isolation (`--sandbox docker`) | ✅ |
| Community leaderboard (opt-in submissions) | 🔜 |

### 🧪 AgentEval Model Evaluation — LLM responses

The original evaluation framework is fully preserved and unchanged:

- 6 providers: OpenAI, Anthropic, Gemini, Groq, Ollama, mock
- 7 suites: codegen, qa, reasoning, summarization, tool-use, adversarial, traces
- Semantic scoring, pass@k, cost/latency tracking, robustness metric
- Local web dashboard (`agenteval serve`), human-in-the-loop review
- Reusable GitHub Actions workflow + Docker image

```bash
agenteval run --provider openai --model gpt-4o-mini --suite all
agenteval serve --dir reports
```

---

## Architecture

```
agenteval/
├── packages/
│   ├── core/               Python package
│   │   └── agenteval/
│   │       ├── arena/      coding-agent battles
│   │       │   ├── agents.py     agent adapters (codex, claude, ...)
│   │       │   ├── workspace.py  git worktree isolation
│   │       │   ├── project.py    ecosystem detection
│   │       │   ├── verifiers.py  test/build/lint/typecheck
│   │       │   ├── regression.py baseline comparison
│   │       │   ├── scoring.py    transparent weighted scoring
│   │       │   ├── arena.py      orchestrator
│   │       │   └── results.py    portable result schema
│   │       ├── cli.py      argparse CLI
│   │       ├── providers.py  model providers
│   │       ├── evaluator.py  model evaluation engine
│   │       ├── traces.py     multi-step tool-call evaluation
│   │       ├── tasks.py      task suites
│   │       └── report.py     JSON + Markdown reports
│   └── sdk-ts/             TypeScript SDK
├── examples/               Runnable examples + sample reports
├── docs/                   Guides (arena, providers, scoring, ...)
└── .github/workflows/      CI + reusable evaluation workflow
```

---

## Roadmap

See [issues](https://github.com/rexblade58/agenteval/issues) for live
tracking. Current focus: **Arena Phase 2+**.

- [x] GitHub issue mode (`agenteval issue https://github.com/.../issues/42`)
- [x] Winning-solution PR creation (`--create-pr`)
- [x] Playwright browser verification (UI checks, console errors, screenshots)
- [x] Docker sandbox isolation for untrusted agent runs
- [ ] OpenCode/Gemini/Aider adapter hardening
- [ ] Portable benchmark packs + opt-in community leaderboard
- [ ] Shareable `AgentEval Verified ✓` badges

Completed (model evaluation): dashboard, semantic scoring, Gemini/Groq
providers, adversarial suite, trace evaluation, human review, reusable CI,
Docker image.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Adding an agent adapter, verifier,
or language runner is a focused, well-documented task:

```text
feat(agent): add Kimi coding agent adapter
feat(runner): add Laravel support
feat(verifier): add Lighthouse performance verifier
```

## License

MIT © [Menard Rosal](https://github.com/rexblade58)
