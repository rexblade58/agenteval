# Contributing to AgentEval

Thanks for your interest! AgentEval is designed to be community-driven — the
more providers and task suites it supports, the more useful it becomes.

## Getting started

1. Fork the repository
2. Clone your fork
3. Create a feature branch: `git checkout -b feature/your-feature`
4. Make your changes
5. Run the tests: `pytest packages/core/tests`
6. Submit a pull request

## What we need help with

- **New providers** — implement `BaseProvider` and register it
- **New task suites** — add tasks to `agenteval/tasks.py`
- **Better scoring** — semantic similarity, LLM-as-judge, partial credit
- **Web dashboard** — visualize historical evaluation results
- **Docs** — tutorials, API references, migration guides

## Adding a provider

1. Subclass `BaseProvider` in `packages/core/agenteval/providers.py`
2. Implement `complete(messages, temperature) -> ProviderResult`
3. Register it in `PROVIDER_REGISTRY`
4. Add a test in `packages/core/tests/test_core.py`

```python
from agenteval.providers import BaseProvider, ProviderResult, Message

class MyProvider(BaseProvider):
    name = "my-provider"

    def __init__(self, model="default", **kwargs):
        self.model = model

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        # ... call your API ...
        return ProviderResult(text=response, latency_ms=elapsed)
```

## Code style

- Python: PEP 8, type hints on all public functions
- TypeScript: strict mode, types exported from `src/types.ts`
- Keep dependencies minimal — no heavy frameworks

## Running tests

```bash
pip install -e "packages/core[dev]"
pytest packages/core/tests
```

## Code of conduct

Be respectful and constructive. All contributions are welcome regardless of
experience level.
