<div align="center">

# 🤖 AgentEval

**Open source agent evaluation framework — score any AI agent across providers with standardized, reproducible benchmarks.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](packages/core/pyproject.toml)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-blue.svg)](packages/sdk-ts/package.json)
[![CI](https://github.com/rexblade58/agenteval/actions/workflows/ci.yml/badge.svg)](https://github.com/rexblade58/agenteval/actions/workflows/ci.yml)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

</div>

---

## Why AgentEval?

Every team building AI agents needs to answer one question:

> **How good is my agent, actually?**

There are frameworks for orchestration (LangChain), observability (Langfuse), and tracking (MLflow) — but **no standardized, provider-agnostic way to score an agent's performance**. AgentEval fills that gap:

- **One command** → comparable scores across OpenAI, Anthropic, Ollama, and local models
- **Standardized task suites** for the capabilities that matter: codegen, QA, reasoning, summarization, tool-use
- **Real metrics**: accuracy, pass@k, latency, cost per run
- **CI-ready**: fail builds when agent quality drops below a threshold

```bash
pip install agenteval
agenteval run --provider openai --model gpt-4o-mini --suite all
```

```text
# AgentEval Report

- Provider: openai (gpt-4o-mini)
- Suite: all
- Tasks: 8/10 passed
- Accuracy: 80.0%
- Avg latency: 420.3 ms
- Total cost: $0.000412
```

---

## Features

| Feature | Description |
| :--- | :--- |
| **Multi-provider** | OpenAI-compatible APIs, Anthropic, Gemini, Groq, Ollama, local models, mock |
| **Task suites** | codegen, qa, reasoning, summarization, tool-use (+ custom) |
| **pass@k** | Run a task N times, pass if any sample succeeds |
| **Cost tracking** | Per-run USD cost for every provider |
| **CLI + SDK** | Python CLI and TypeScript SDK (typed, tested) |
| **CI integration** | Non-zero exit below threshold; JSON output |
| **Zero heavy deps** | httpx + rich only — no framework lock-in |

---

## Status

**Actively developed.** Current state of the repo:

| Area | Status |
| :--- | :--- |
| Python core (CLI, providers, evaluator, reports) | ✅ Done — 9 unit tests |
| TypeScript SDK (types + mock runner + CLI wrapper) | ✅ Done — 4 unit tests, strict TS |
| CI pipeline | ✅ Python 3.10/3.11/3.12 + TS typecheck/test |
| Mock provider (keyless testing) | ✅ Done |
| Providers: OpenAI, Anthropic, Ollama, mock | ✅ Done |
| Gemini provider | ✅ Done — `--provider gemini` |
| Groq provider (free tier) | ✅ Done — `--provider groq` |
| Semantic scoring (`--scoring semantic`) | ✅ Done |
| pass@k + cost + latency metrics | ✅ Done |
| Web dashboard (`agenteval serve`) | ✅ Done — local, zero-dep |

See the [issues](https://github.com/rexblade58/agenteval/issues) for what's next and [CHANGELOG-style commit history](https://github.com/rexblade58/agenteval/commits/main) for recent progress.

## Quick start

### Mock (no API key)

```bash
git clone https://github.com/rexblade58/agenteval.git
cd agenteval
pip install -e packages/core
agenteval run --provider mock --suite all
```

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
agenteval run --provider openai --model gpt-4o-mini --suite codegen \
  --format json --output reports/openai-codegen.json
```

Reports are written in a stable JSON schema (`schema_version`, `generated_at`,
metrics, per-task results) — see `examples/reports/` for samples.

### Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
agenteval run --provider anthropic --model claude-3-5-sonnet-latest --suite qa
```

### Google Gemini

```bash
export GEMINI_API_KEY=AIza...
agenteval run --provider gemini --model gemini-2.0-flash --suite reasoning
```

### Groq (free tier)

```bash
export GROQ_API_KEY=gsk_...
agenteval run --provider groq --model llama-3.3-70b-versatile --suite codegen
```

### Semantic scoring (paraphrase-tolerant)

```bash
agenteval run --provider mock --suite qa --scoring semantic
```

### Local (Ollama)

```bash
agenteval run --provider ollama --model llama3.2 --suite reasoning
```

### Web dashboard

```bash
agenteval run --provider mock --suite all --output reports/mock.json
agenteval serve --dir reports
# → http://127.0.0.1:8000  (accuracy/cost/latency trends, provider comparison)
```

### TypeScript SDK

```typescript
import { evaluateMock, runCli } from '@agenteval/sdk';

const report = runCli({
  provider: 'openai',
  model: 'gpt-4o-mini',
  suite: 'codegen',
});
console.log(`Accuracy: ${(report.accuracy * 100).toFixed(1)}%`);
```

---

## Architecture

```
agenteval/
├── packages/
│   ├── core/               Python evaluation engine
│   │   └── agenteval/
│   │       ├── cli.py      argparse CLI
│   │       ├── providers.py  OpenAI / Anthropic / Ollama / mock
│   │       ├── evaluator.py  pass@k engine + scoring
│   │       ├── tasks.py      built-in task suites
│   │       └── report.py     JSON + Markdown reports
│   └── sdk-ts/             TypeScript SDK
├── examples/               Runnable examples + sample reports
├── docs/                   Guides
└── .github/workflows/      CI (tests, lint, publish)
```

---

## Adding a provider

Providers implement a single method:

```python
class MyProvider(BaseProvider):
    name = "my-provider"

    def complete(self, messages, temperature=0.7) -> ProviderResult:
        # call your API, return ProviderResult(text=..., latency_ms=..., ...)
        ...
```

Register it in `PROVIDER_REGISTRY` and it works with the CLI, SDK, and reporting — no other changes needed.

---

## Roadmap

Planned work is tracked as [GitHub issues](https://github.com/rexblade58/agenteval/issues) — community PRs are very welcome.

- [x] [Web dashboard with historical comparisons](https://github.com/rexblade58/agenteval/issues/4) — `agenteval serve`
- [x] [Semantic similarity scoring for QA tasks](https://github.com/rexblade58/agenteval/issues/2) — `--scoring semantic`
- [x] [Google Gemini provider](https://github.com/rexblade58/agenteval/issues/1) — `--provider gemini`
- [x] [Groq provider with free-tier models](https://github.com/rexblade58/agenteval/issues/3) — `--provider groq`
- [ ] Human-in-the-loop task review
- [ ] Adversarial / robustness evaluation
- [ ] Agent trace evaluation (multi-step tool calls)
- [ ] Docker image for self-hosting
- [ ] GitHub Actions reusable workflow

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports, provider PRs, and new task suites are all welcome.

## License

MIT © [Menard Rosal](https://github.com/rexblade58)
