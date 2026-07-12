# Providers

AgentEval supports any LLM through a small provider interface. Every provider
returns a `ProviderResult` with the response text, latency, token counts, and
cost — so scoring is identical regardless of backend.

## Supported providers

| Provider | Name | Notes |
| :--- | :--- | :--- |
| Mock | `mock` | Deterministic, offline, for tests and CI |
| OpenAI | `openai` | Also works with any OpenAI-compatible API (DeepSeek, Together, Groq, vLLM, LM Studio) |
| Anthropic | `anthropic` | Claude models via the Messages API |
| Ollama | `ollama` | Local models, zero cost |

## Configuration

Providers are configured through the CLI flags or environment variables:

| Provider | Env var | CLI flag |
| :--- | :--- | :--- |
| openai | `OPENAI_API_KEY` | `--api-key`, `--base-url` |
| anthropic | `ANTHROPIC_API_KEY` | `--api-key` |
| ollama | `OLLAMA_HOST` | `--host` |

## OpenAI-compatible endpoints

Set `OPENAI_BASE_URL` to point at any compatible server:

```bash
# DeepSeek
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://api.deepseek.com/v1
agenteval run --provider openai --model deepseek-chat

# Local vLLM
export OPENAI_BASE_URL=http://localhost:8000/v1
agenteval run --provider openai --model my-model
```

## Adding a provider

Subclass `BaseProvider`, implement `complete()`, register it:

```python
from agenteval.providers import BaseProvider, ProviderResult, Message

class MyProvider(BaseProvider):
    name = "my-provider"

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        ...
        return ProviderResult(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
        )

from agenteval.providers import PROVIDER_REGISTRY
PROVIDER_REGISTRY["my-provider"] = MyProvider
```
