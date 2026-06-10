<div align="center">

# 🤖 AgentEval

**Open source agent evaluation framework — score any AI agent across providers with standardized, reproducible benchmarks.**

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](packages/core/pyproject.toml)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0%2B-blue.svg)](packages/sdk-ts/package.json)
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
| **Multi-provider** | OpenAI-compatible APIs, Anthropic, Ollama, local models, mock |
| **Task suites** | codegen, qa, reasoning, summarization, tool-use (+ custom) |
| **pass@k** | Run a task N times, pass if any sample succeeds |
| **Cost tracking** | Per-run USD cost for every provider |
| **CLI + SDK** | Python CLI and TypeScript SDK |
| **CI integration** | Non-zero exit below threshold; JSON output |
| **Zero heavy deps** | httpx + rich only — no framework lock-in |

---

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
agenteval run --provider openai --model gpt-4o-mini --suite codegen
```

### Anthropic

```bash
export ANTHROPIC_API_KEY=sk-ant-...
agenteval run --provider anthropic --model claude-3-5-sonnet-latest --suite qa
```

### Local (Ollama)

```bash
agenteval run --provider ollama --model llama3.2 --suite reasoning
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
├── examples/               Runnable examples
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

- [ ] Web dashboard with historical comparisons
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
