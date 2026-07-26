"""AgentEval - trace evaluation.

Real agents take multiple steps: they call tools, observe results, and
recover from mistakes. Trace evaluation drives that loop and scores:

- **success**: did the agent reach the goal?
- **tool validity**: fraction of tool calls that were valid
- **efficiency**: steps used vs the step budget

Tool calls are parsed from provider output using the line format:

    TOOL {"name": "tool_name", "args": {"key": "value"}}

A response with no TOOL lines is treated as the final answer.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .providers import BaseProvider, Message

TOOL_LINE = re.compile(r'^TOOL\s+(\{.*?\})\s*$', re.MULTILINE | re.DOTALL)


@dataclass
class ToolSpec:
    """A tool an agent may call during a trace."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """A parsed tool invocation from provider output."""

    name: str
    args: dict[str, Any]
    valid: bool = False
    observation: str = ""


@dataclass
class TraceScenario:
    """A multi-step agent task with a simulated tool environment."""

    id: str
    category: str
    prompt: str
    tools: list[ToolSpec]
    goal: str  # human description of success (used in reports)
    max_steps: int = 6
    # executor(name, args, state) -> observation string, mutating state
    executor: Callable[[str, dict[str, Any], dict[str, Any]], str] | None = None
    # goal_check(state) -> bool, defaults to goal keyword in final answer
    goal_check: Callable[[dict[str, Any], str], bool] | None = None
    initial_state: dict[str, Any] = field(default_factory=dict)
    description: str = ""


@dataclass
class TraceResult:
    """Outcome of running one trace scenario."""

    trace_id: str
    success: bool
    steps: int
    max_steps: int
    tool_calls_total: int
    tool_calls_valid: int
    final_answer: str = ""
    error: str | None = None

    @property
    def tool_validity(self) -> float:
        return self.tool_calls_valid / self.tool_calls_total if self.tool_calls_total else 1.0

    @property
    def efficiency(self) -> float:
        """1.0 = finished in one step; 0.0 = exhausted the step budget."""
        if self.max_steps <= 1:
            return 1.0
        return max(0.0, (self.max_steps - self.steps) / (self.max_steps - 1))


def parse_tool_calls(text: str) -> list[ToolCall]:
    """Parse TOOL lines from provider output."""
    calls: list[ToolCall] = []
    for match in TOOL_LINE.finditer(text):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            args = data.get("args", {})
            calls.append(ToolCall(name=data["name"], args=args if isinstance(args, dict) else {}))
    return calls


class TraceEvaluator:
    """Runs trace scenarios against a provider in an agent loop."""

    def __init__(self, provider: BaseProvider, suite: str = "traces", max_steps: int | None = None):
        self.provider = provider
        self.suite = suite
        self._max_steps = max_steps

    def _tool_by_name(self, scenario: TraceScenario, name: str) -> ToolSpec | None:
        return next((t for t in scenario.tools if t.name == name), None)

    def run_scenario(self, scenario: TraceScenario) -> TraceResult:
        max_steps = self._max_steps or scenario.max_steps
        state: dict[str, Any] = dict(scenario.initial_state)
        messages: list[Message] = [
            Message(role="system", content=(
                "You are an agent being evaluated. Use the available tools by "
                "emitting exactly one line: TOOL {\"name\": \"...\", \"args\": {...}}.\n"
                "After observing results, either call another tool or give the final answer."
            )),
            Message(role="user", content=scenario.prompt),
        ]

        steps = 0
        total_calls = 0
        valid_calls = 0
        final_answer = ""
        error: str | None = None

        while steps < max_steps:
            steps += 1
            try:
                resp = self.provider.complete(messages, temperature=0.2)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                break
            text = resp.text
            calls = parse_tool_calls(text)

            if not calls:
                final_answer = text.strip()
                break

            for call in calls:
                total_calls += 1
                tool = self._tool_by_name(scenario, call.name)
                if tool is None:
                    call.valid = False
                    observation = f"error: unknown tool '{call.name}'"
                else:
                    try:
                        if scenario.executor:
                            observation = scenario.executor(call.name, call.args, state)
                        else:
                            observation = "ok"
                        call.valid = True
                        valid_calls += 1
                    except Exception as exc:  # noqa: BLE001
                        observation = f"error: {exc}"
                messages.append(Message(role="assistant", content=f'TOOL {json.dumps({"name": call.name, "args": call.args})}'))
                messages.append(Message(role="user", content=f"observation: {observation}"))

        if not final_answer and error is None:
            error = f"exhausted {max_steps} steps without a final answer"

        if scenario.goal_check:
            success = bool(scenario.goal_check(state, final_answer))
        else:
            success = bool(final_answer) and scenario.goal.lower() in final_answer.lower()

        return TraceResult(
            trace_id=scenario.id,
            success=success,
            steps=steps,
            max_steps=max_steps,
            tool_calls_total=total_calls,
            tool_calls_valid=valid_calls,
            final_answer=final_answer,
            error=error,
        )

    def run_suite(self, suite_name: str | None = None) -> list[TraceResult]:
        scenarios = get_traces(suite_name or self.suite)
        return [self.run_scenario(s) for s in scenarios]


TRACE_REGISTRY: dict[str, list[TraceScenario]] = {}


def get_traces(suite: str = "traces") -> list[TraceScenario]:
    if suite not in TRACE_REGISTRY:
        raise ValueError(f"Unknown trace suite '{suite}'. Available: {', '.join(TRACE_REGISTRY)}")
    return TRACE_REGISTRY[suite]


__all__ = [
    "TraceScenario",
    "TraceResult",
    "TraceEvaluator",
    "ToolSpec",
    "ToolCall",
    "parse_tool_calls",
    "get_traces",
    "TRACE_REGISTRY",
]
