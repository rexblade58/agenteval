"""AgentEval - open source agent evaluation framework.

Score any AI agent across providers with standardized, reproducible
benchmarks.

Quick start:
    pip install -e packages/core
    agenteval run --provider mock --suite all
    agenteval run --provider openai --model gpt-4o-mini --suite codegen
"""

from .providers import (
    BaseProvider,
    Message,
    ProviderResult,
    MockProvider,
    OpenAIProvider,
    AnthropicProvider,
    OllamaProvider,
    create_provider,
)
from .tasks import Task, get_tasks
from .evaluator import Evaluator, EvaluationReport, TaskResult

__version__ = "0.1.0"

__all__ = [
    "BaseProvider",
    "Message",
    "ProviderResult",
    "MockProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "OllamaProvider",
    "create_provider",
    "Task",
    "get_tasks",
    "Evaluator",
    "EvaluationReport",
    "TaskResult",
    "__version__",
]
