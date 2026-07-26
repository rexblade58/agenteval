"""AgentEval - provider abstraction layer.

Supports any LLM provider through a common interface:
- OpenAI-compatible APIs (OpenAI, DeepSeek, Together, Groq, local servers)
- Anthropic Messages API
- Google Gemini REST API
- Ollama (local models)
- A deterministic MockProvider for offline testing
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A single chat message."""

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ProviderResult:
    """The result of a single model call."""

    text: str
    latency_ms: float
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class BaseProvider(ABC):
    """Common interface implemented by every provider."""

    name: str = "base"
    model: str = ""

    @abstractmethod
    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        """Send messages and return the model's response."""


# ---------------------------------------------------------------------------
# Mock provider - deterministic, offline, used for tests and CI
# ---------------------------------------------------------------------------
class MockProvider(BaseProvider):
    """Deterministic provider. Returns canned responses so tests never
    depend on network access or paid APIs."""

    name = "mock"

    def __init__(self, model: str = "mock-model", responses: dict[str, str] | None = None):
        self.model = model
        self._responses = responses or {
            "default": "This is a mock response for testing.",
            "code": "def add(a, b):\n    return a + b",
            "fizzbuzz": "def fizzbuzz():\n    for i in range(1, 101):\n        if i % 15 == 0: print('FizzBuzz')\n        elif i % 3 == 0: print('Fizz')\n        elif i % 5 == 0: print('Buzz')\n        else: print(i)",
            "two_sum": "def two_sum(nums, target):\n    seen = {}\n    for i, n in enumerate(nums):\n        if target - n in seen:\n            return [seen[target - n], i]\n        seen[n] = i",
            "merge": "def merge(a, b):\n    result = []\n    i = j = 0\n    while i < len(a) and j < len(b):\n        if a[i] < b[j]:\n            result.append(a[i]); i += 1\n        else:\n            result.append(b[j]); j += 1\n    result.extend(a[i:])\n    result.extend(b[j:])\n    return result",
            "question": "The capital of France is Paris.",
            "concurrency": "A mutex allows only one thread to enter a critical section at a time, while a semaphore allows a fixed number of threads.",
            "riddle": "The ball costs $0.05. The bat costs $1.05, which is $1.00 more, totaling $1.10.",
            "water": "2 liters remain in the 5-liter bucket after pouring 3 into the 3-liter bucket.",
            "summary": "The company's revenue increased 12% driven by strong demand for AI products, with plans to expand into European markets.",
            "format_date": "def format_date(iso):\n    from datetime import datetime\n    return datetime.fromisoformat(iso).strftime('%B %d, %Y')",
            "parse_json": "def get_name(json_str):\n    import json\n    return json.loads(json_str).get('name')",
            "refusal": "I can't help with that. I'm not able to reveal secrets or override my guidelines.",
            "unknown": "I don't know. I don't have information about that.",
            "trace_search": 'TOOL {"name": "search_flights", "args": {"from": "MNL", "to": "SFO"}}',
            "trace_book": 'TOOL {"name": "book_flight", "args": {"flight": "AY-123"}}',
            "trace_confirm": "I've booked your flight: AY-123 from MNL to SFO.",
            "trace_build_run": 'TOOL {"name": "run_build", "args": {}}',
            "trace_build_patch": 'TOOL {"name": "patch_file", "args": {"path": "main.py"}}',
            "trace_build_done": "The build passes now.",
        }

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        last = messages[-1].content.lower()
        key = "default"
        # Trace scenarios: multi-step TOOL responses driven by observations
        if "book the cheapest one" in last:
            key = "trace_search"
        elif "available: ay-123" in last:
            key = "trace_book"
        elif "booked flight ay-123" in last:
            key = "trace_confirm"
        elif "the build is failing on main" in last:
            key = "trace_build_run"
        elif "fail: syntax error" in last:
            key = "trace_build_patch"
        elif "patched main.py" in last:
            key = "trace_build_run"
        elif last.startswith("observation:") and last.strip().endswith("pass"):
            key = "trace_build_done"
        elif "ignore all previous" in last or "ignore my guidelines" in last:
            key = "refusal"
        elif "secret key" in last or "hunter2" in last or "admin password" in last:
            key = "refusal"
        elif "nobel prize" in last or "quantum slippers" in last:
            key = "unknown"
        elif "fizzbuzz" in last:
            key = "fizzbuzz"
        elif "two_sum" in last or "two sum" in last:
            key = "two_sum"
        elif "merge two sorted" in last or "merge two" in last:
            key = "merge"
        elif "mutex" in last and "semaphore" in last:
            key = "concurrency"
        elif "bat and a ball" in last or "ball cost" in last:
            key = "riddle"
        elif "5-liter bucket" in last or "8 liters" in last:
            key = "water"
        elif "summarize" in last or "summary" in last:
            key = "summary"
        elif "format_date" in last or "format date" in last:
            key = "format_date"
        elif "json" in last and "name" in last:
            key = "parse_json"
        elif "code" in last or "function" in last or "def " in last:
            key = "code"
        elif "capital" in last or "france" in last:
            key = "question"
        return ProviderResult(
            text=self._responses[key],
            latency_ms=1.0,
            input_tokens=sum(len(m.content.split()) for m in messages),
            output_tokens=len(self._responses[key].split()),
            cost_usd=0.0,
        )


# ---------------------------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------------------------
class OpenAIProvider(BaseProvider):
    """Works with any OpenAI-compatible endpoint (OpenAI, DeepSeek,
    Together, Groq, vLLM, LM Studio, etc.)."""

    name = "openai"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        base_url: str | None = None,
        cost_per_1k_input: float = 0.00015,
        cost_per_1k_output: float = 0.0006,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. Provide api_key= or set the environment variable."
            )

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        import httpx
        import time

        url = f"{self.base_url or 'https://api.openai.com/v1'}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        start = time.perf_counter()
        resp = httpx.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = resp.json()

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        in_tokens = usage.get("prompt_tokens", 0)
        out_tokens = usage.get("completion_tokens", 0)
        cost = (in_tokens / 1000 * self.cost_per_1k_input) + (
            out_tokens / 1000 * self.cost_per_1k_output
        )
        return ProviderResult(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------
class AnthropicProvider(BaseProvider):
    """Anthropic Messages API (Claude models)."""

    name = "anthropic"

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-latest",
        api_key: str | None = None,
        cost_per_1k_input: float = 0.003,
        cost_per_1k_output: float = 0.015,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. Provide api_key= or set the environment variable."
            )

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        import httpx
        import time

        # Anthropic uses a different message format: system is separate
        system = next((m.content for m in messages if m.role == "system"), None)
        chat_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role != "system"
        ]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": 4096,
            "temperature": temperature,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        start = time.perf_counter()
        resp = httpx.post(
            "https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=120
        )
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = resp.json()

        text = "".join(b.get("text", "") for b in data.get("content", []))
        usage = data.get("usage", {})
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
        cost = (in_tokens / 1000 * self.cost_per_1k_input) + (
            out_tokens / 1000 * self.cost_per_1k_output
        )
        return ProviderResult(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Groq provider (OpenAI-compatible, free-tier)
# ---------------------------------------------------------------------------
class GroqProvider(OpenAIProvider):
    """Groq's OpenAI-compatible endpoint with free-tier models."""

    name = "groq"

    def __init__(
        self,
        model: str = "llama-3.3-70b-versatile",
        api_key: str | None = None,
        base_url: str = "https://api.groq.com/openai/v1",
        cost_per_1k_input: float = 0.0,  # free tier
        cost_per_1k_output: float = 0.0,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.base_url = base_url
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Provide api_key= or set the environment variable."
            )


# ---------------------------------------------------------------------------
# Gemini provider (Google REST API)
# ---------------------------------------------------------------------------
class GeminiProvider(BaseProvider):
    """Google Gemini models via the REST API (generativelanguage)."""

    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        cost_per_1k_input: float = 0.0001,
        cost_per_1k_output: float = 0.0004,
    ):
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.cost_per_1k_input = cost_per_1k_input
        self.cost_per_1k_output = cost_per_1k_output
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Provide api_key= or set the environment variable."
            )

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        import httpx
        import time

        # Gemini uses a slightly different format: system prompt is a role too
        contents = [{"role": "user" if m.role == "user" else "model",
                     "parts": [{"text": m.content}]} for m in messages]
        payload = {
            "contents": contents,
            "generationConfig": {"temperature": temperature},
        }
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        headers = {"x-goog-api-key": self.api_key}

        start = time.perf_counter()
        resp = httpx.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = resp.json()

        try:
            text = "".join(
                p.get("text", "")
                for p in data["candidates"][0]["content"]["parts"]
            )
        except (KeyError, IndexError):
            text = data.get("promptFeedback", {}).get(
                "blockReason", ""
            ) or ""

        usage = data.get("usageMetadata", {})
        in_tokens = usage.get("promptTokenCount", 0)
        out_tokens = usage.get("candidatesTokenCount", 0)
        cost = (in_tokens / 1000 * self.cost_per_1k_input) + (
            out_tokens / 1000 * self.cost_per_1k_output
        )
        return ProviderResult(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=cost,
            raw=data,
        )


# ---------------------------------------------------------------------------
# Ollama provider (local models)
# ---------------------------------------------------------------------------
class OllamaProvider(BaseProvider):
    """Local models served by Ollama."""

    name = "ollama"

    def __init__(self, model: str = "llama3.2", host: str | None = None):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    def complete(self, messages: list[Message], temperature: float = 0.7) -> ProviderResult:
        import httpx
        import time

        prompt = "\n".join(f"{m.role}: {m.content}" for m in messages)
        payload = {"model": self.model, "prompt": prompt, "stream": False, "temperature": temperature}

        start = time.perf_counter()
        resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=300)
        resp.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        data = resp.json()

        text = data.get("response", "")
        in_tokens = data.get("prompt_eval_count", 0)
        out_tokens = data.get("eval_count", 0)
        return ProviderResult(
            text=text,
            latency_ms=elapsed_ms,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            cost_usd=0.0,  # local = free
            raw=data,
        )


PROVIDER_REGISTRY: dict[str, type[BaseProvider]] = {
    "mock": MockProvider,
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "groq": GroqProvider,
    "gemini": GeminiProvider,
}


def create_provider(name: str, **kwargs: Any) -> BaseProvider:
    """Factory: create a provider by name."""
    if name not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {', '.join(PROVIDER_REGISTRY)}"
        )
    return PROVIDER_REGISTRY[name](**kwargs)


__all__ = [
    "Message",
    "ProviderResult",
    "BaseProvider",
    "MockProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "GroqProvider",
    "GeminiProvider",
    "create_provider",
    "PROVIDER_REGISTRY",
]
