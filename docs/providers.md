# Providers

AgentEval supports any LLM through a small provider interface. Every provider
returns a `ProviderResult` with the response text, latency, token counts, and
cost — so scoring is identical regardless of backend.

## Supported providers

| Provider | Name | Notes |
| :--- | :--- | :--- |
| Mock | `mock` | Deterministic, offline, for tests and CI |
| OpenAI | `openai` | Also works with any OpenAI-compatible API (DeepSeek, Together, vLLM, LM Studio) |
| Anthropic | `anthropic` | Claude models via the Messages API |
| Google Gemini | `gemini` | Gemini 2.0 family via the REST API |
| Groq | `groq` | Fast free-tier models, OpenAI-compatible |
| Ollama | `ollama` | Local models, zero cost |

## Configuration

Providers are configured through the CLI flags or environment variables:

| Provider | Env var | CLI flag |
| :--- | :--- | :--- |
| openai | `OPENAI_API_KEY` | `--api-key`, `--base-url` |
| anthropic | `ANTHROPIC_API_KEY` | `--api-key` |
| gemini | `GEMINI_API_KEY` | `--api-key` |
| groq | `GROQ_API_KEY` | `--api-key`, `--base-url` |
| ollama | `OLLAMA_HOST` | `--host` |

```bash
# Gemini
export GEMINI_API_KEY=AIza...
agenteval run --provider gemini --model gemini-2.0-flash --suite reasoning

# Groq (free tier)
export GROQ_API_KEY=gsk_...
agenteval run --provider groq --model llama-3.3-70b-versatile --suite codegen
```

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
