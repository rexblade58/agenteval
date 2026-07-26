"""AgentEval - built-in trace suites.

Each scenario simulates a small tool environment (stateful executors) so
agents can be scored on multi-step tool use without real backends.
"""

from __future__ import annotations

from typing import Any

from .traces import TRACE_REGISTRY, ToolSpec, TraceScenario

# ---------------------------------------------------------------------------
# Book a flight
# ---------------------------------------------------------------------------
def _book_executor(name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
    if name == "search_flights":
        return "Available: AY-123 from MNL to SFO at $450 (2 stops left)"
    if name == "book_flight":
        state["booked"] = True
        return "Booked flight AY-123 for you."
    if name == "cancel_flight":
        state["booked"] = False
        return "Cancelled flight AY-123."
    raise ValueError(f"unknown tool '{name}'")


BOOK_FLIGHT = TraceScenario(
    id="trace-book-flight",
    category="traces",
    description="Book a flight using search and booking tools.",
    prompt=(
        "I need to fly from Manila (MNL) to San Francisco (SFO) next week. "
        "Search for a flight and book the cheapest one, then confirm."
    ),
    tools=[
        ToolSpec(
            name="search_flights",
            description="Search flights. Returns available flights with prices.",
            parameters={"from": "str", "to": "str"},
        ),
        ToolSpec(
            name="book_flight",
            description="Book a flight by its identifier.",
            parameters={"flight": "str"},
        ),
        ToolSpec(
            name="cancel_flight",
            description="Cancel a booked flight.",
            parameters={"flight": "str"},
        ),
    ],
    goal="booked",
    max_steps=5,
    executor=_book_executor,
    goal_check=lambda state, _answer: bool(state.get("booked")),
    initial_state={},
)

# ---------------------------------------------------------------------------
# Fix a failing build
# ---------------------------------------------------------------------------
def _build_executor(name: str, args: dict[str, Any], state: dict[str, Any]) -> str:
    if name == "run_build":
        if state.get("patched"):
            state["build_ok"] = True
            return "PASS"
        return "FAIL: syntax error in main.py line 4"
    if name == "read_file":
        return "def main():\n    print('hello')\n\nmain(  # missing paren"
    if name == "patch_file":
        state["patched"] = True
        return f"patched {args.get('path', 'main.py')}"
    raise ValueError(f"unknown tool '{name}'")


FIX_BUILD = TraceScenario(
    id="trace-fix-build",
    category="traces",
    description="Diagnose and fix a failing build.",
    prompt=(
        "The build is failing on main. Inspect the failure, fix the file, "
        "and verify the build passes."
    ),
    tools=[
        ToolSpec(
            name="run_build",
            description="Run the build. Returns PASS or FAIL with diagnostics.",
        ),
        ToolSpec(
            name="read_file",
            description="Read a file from the repo.",
            parameters={"path": "str"},
        ),
        ToolSpec(
            name="patch_file",
            description="Apply a fix to a file.",
            parameters={"path": "str", "content": "str"},
        ),
    ],
    goal="build passes",
    max_steps=6,
    executor=_build_executor,
    goal_check=lambda state, _answer: bool(state.get("build_ok")),
    initial_state={},
)

TRACE_REGISTRY["traces"] = [BOOK_FLIGHT, FIX_BUILD]

__all__ = ["BOOK_FLIGHT", "FIX_BUILD"]
