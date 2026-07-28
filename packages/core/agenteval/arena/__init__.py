"""AgentEval Arena - make AI agents prove their code works.

Arena runs multiple autonomous coding agents against the same real task in
isolated git worktrees, verifies each result with real commands, detects
regressions, and ranks the attempts objectively.
"""

from .agents import (
    AgentAdapter,
    AgentRunResult,
    AgentStatus,
    CommandAgent,
    CodexAgent,
    ClaudeCodeAgent,
    GeminiCliAgent,
    OpenCodeAgent,
    AiderAgent,
    create_agent,
    list_agents,
)
from .arena import ArenaConfig, ArenaRunner
from .results import AgentResult, ArenaResult
from .workspace import WorktreeManager

__all__ = [
    "AgentAdapter",
    "AgentRunResult",
    "AgentStatus",
    "CommandAgent",
    "CodexAgent",
    "ClaudeCodeAgent",
    "GeminiCliAgent",
    "OpenCodeAgent",
    "AiderAgent",
    "create_agent",
    "list_agents",
    "ArenaConfig",
    "ArenaRunner",
    "AgentResult",
    "ArenaResult",
    "WorktreeManager",
]
