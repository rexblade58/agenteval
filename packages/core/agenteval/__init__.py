"""AgentEval - open source agent evaluation and battle platform.

Two workflows:

- **Model evaluation**: score LLM responses across providers
  (`agenteval run --provider mock --suite all`)
- **Arena**: battle autonomous coding agents against a real repository task
  in isolated worktrees (`agenteval arena --repo . --task "..." --agents codex,claude`)

Quick start:
    pip install -e packages/core
    agenteval run --provider mock --suite all
    agenteval arena --repo . --task "fix the failing checkout test" --agents codex,claude
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

__version__ = "0.2.0"

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
