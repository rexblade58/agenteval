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

- **New agents** — implement `AgentAdapter` for a coding agent CLI
- **New providers** — implement `BaseProvider` and register it
- **New verifiers** — implement `Verifier` (tests, browser, visual, ...)
- **New task suites** — add tasks to `agenteval/tasks.py`
- **Better scoring** — semantic similarity, LLM-as-judge, partial credit
- **Arena scenarios** — fixture repositories and trace scenarios
- **Docs** — tutorials, API references, migration guides

## Adding a coding agent adapter

Agents are the arena equivalent of providers. Implement `AgentAdapter` in
`agenteval/arena/agents.py` (or subclass `CommandAgent` for CLI wrappers)
and register it in `AGENT_REGISTRY`:

```python
from agenteval.arena.agents import CommandAgent

class MyAgent(CommandAgent):
    name = "my-agent"
    display_name = "My Agent CLI"
    description = "Runs my-agent in headless mode"

    def __init__(self, timeout_s: int = 900, extra_args: str = ""):
        template = f"my-agent run {extra_args} {{task}}"
        super().__init__(template, name="my-agent", timeout_s=timeout_s)

    def available(self) -> bool:
        return shutil.which("my-agent") is not None
```

Add a unit test with a mock executable — never call paid APIs in CI.

## Adding a verifier

```python
from agenteval.arena.verifiers import Verifier, VerificationResult

class MyVerifier(Verifier):
    name = "security"

    def verify(self, workspace, profile) -> VerificationResult:
        # run real commands, return structured VerificationResult
        ...
```

Register it in `VERIFIER_REGISTRY` and it appears in `agenteval verifiers list`.

## Adding a language runner

Extend `detect()` in `agenteval/arena/project.py` with the ecosystem's
manifest files and default install/test/build/lint/typecheck commands.
Detection must never run commands — it only *suggests* them.

## Running tests

```bash
pip install -e "packages/core[dev]"
pytest packages/core/tests

# TypeScript SDK
cd packages/sdk-ts
npm install
npm test          # vitest
npm run typecheck # tsc --noEmit
```

## Adding a provider

Providers turn an LLM API into a `complete(messages) -> ProviderResult` call.
Adding one is a focused, testable contribution — see the existing providers in
`packages/core/agenteval/providers.py` for reference.

### Steps

1. **Subclass `BaseProvider`** in `packages/core/agenteval/providers.py`
2. **Implement `complete(messages, temperature) -> ProviderResult`**
3. **Register it** in `PROVIDER_REGISTRY`
4. **Add tests** in `packages/core/tests/test_core.py` using a fake transport
   (never hit a real API in tests)
5. **Document it** in `docs/providers.md` and update the status table in
   `README.md`

### Template

```python
from agenteval.providers import BaseProvider, ProviderResult, Message

class MyProvider(BaseProvider):
    name = "my-provider"

    def __init__(self, model="default", api_key=None):
        self.model = model
        self.api_key = api_key or os.environ.get("MY_API_KEY", "")
        if not self.api_key:
            raise ValueError("MY_API_KEY is not set")

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        import httpx  # imported lazily so the CLI stays fast
        import time

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        start = time.perf_counter()
        resp = httpx.post("https://api.example.com/v1/chat", json=payload,
                          headers={"Authorization": f"Bearer {self.api_key}"}, timeout=120)
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = resp.json()

        return ProviderResult(
            text=data["choices"][0]["message"]["content"],
            latency_ms=elapsed_ms,
            input_tokens=data.get("usage", {}).get("prompt_tokens", 0),
            output_tokens=data.get("usage", {}).get("completion_tokens", 0),
            cost_usd=0.0,  # fill in real pricing per 1k tokens
            raw=data,
        )
```

### Checklist for providers

- [ ] Environment variable convention: `{NAME}_API_KEY` (uppercase, documented)
- [ ] `cost_usd` computed from real published pricing per 1k tokens
- [ ] `httpx` imported lazily inside `complete()` (keeps CLI startup fast)
- [ ] Registered in `PROVIDER_REGISTRY` (CLI `--provider` accepts it automatically)
- [ ] Unit test with a fake/mocked transport — no network calls in CI
- [ ] Documented in `docs/providers.md` + `README.md` status table

### Testing a provider without an API key

The `mock` provider is deterministic and needs no network. Use it as the
baseline for any suite: `agenteval run --provider mock --suite all`.


## Code style

- Python: PEP 8, type hints on all public functions
- TypeScript: strict mode, types exported from `src/types.ts`
- Keep dependencies minimal — no heavy frameworks

## Running tests

```bash
pip install -e "packages/core[dev]"
pytest packages/core/tests

# TypeScript SDK
cd packages/sdk-ts
npm install
npm test          # vitest
npm run typecheck # tsc --noEmit
```

## Sample reports

`examples/reports/` contains sample JSON evaluation reports that demonstrate
the report schema (also used by the future web dashboard). Regenerate them with:

```bash
python examples/generate_sample_reports.py
```

## Arena test fixtures

`packages/core/tests/fixtures/` holds small fixture repositories used by the
arena tests:

- `python-app/` — a pytest project with a deliberately broken discount
  function (baseline has failing tests; `fix_discount.py` simulates a
  fixing agent)
- `sleep.py` — an agent that hangs (timeout tests)

Add fixture repositories for new ecosystems as needed.

## Code of conduct

Be respectful and constructive. All contributions are welcome regardless of
experience level.
