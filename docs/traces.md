# Trace evaluation

Real agents rarely succeed in a single call — they call tools, observe
results, and recover. Trace evaluation drives that loop and scores the
whole trajectory, not just the final answer.

## Running traces

```bash
agenteval run --provider openai --model gpt-4o-mini --suite traces
```

With the mock provider (deterministic, offline):

```bash
agenteval run --provider mock --suite traces
```

## How it works

1. The agent receives the scenario prompt plus a system message describing
   the tool-call protocol.
2. On each step the provider may emit one or more tool calls as lines:

   ```
   TOOL {"name": "search_flights", "args": {"from": "MNL", "to": "SFO"}}
   ```

3. Each tool call is executed against a simulated environment; the
   observation is appended to the conversation.
4. A response with no `TOOL` lines is treated as the final answer.
5. If the step budget is exhausted without a final answer, the trace fails.

## Metrics

| Metric | Definition |
| :--- | :--- |
| **Success** | The goal state was reached (scenario-specific, state-based) |
| **Tool validity** | Valid tool calls / total tool calls (unknown tools and executor errors count against it) |
| **Efficiency** | `(max_steps - steps) / (max_steps - 1)` — 1.0 = done in one step |

The trace report is included in the JSON output under the `trace` key and in
Markdown as a "Trace results" section.

## Built-in scenarios

| Trace | Tools | Goal |
| :--- | :--- | :--- |
| `trace-book-flight` | `search_flights`, `book_flight`, `cancel_flight` | A flight is booked |
| `trace-fix-build` | `run_build`, `read_file`, `patch_file` | The build passes |

## Custom scenarios

Scenarios are data: give a prompt, a tool list, an executor function, and a
goal check, then register it.

```python
from agenteval.traces import TraceEvaluator, TraceScenario, ToolSpec, TRACE_REGISTRY

def executor(name, args, state):
    if name == "ping":
        state["pong"] = True
        return "pong"
    raise ValueError(f"unknown tool '{name}'")

scenario = TraceScenario(
    id="trace-ping",
    category="traces",
    description="Call ping once.",
    prompt="Call the ping tool and report the result.",
    tools=[ToolSpec(name="ping", description="Returns pong.")],
    goal="pinged",
    max_steps=3,
    executor=executor,
    goal_check=lambda state, answer: bool(state.get("pong")),
)

TRACE_REGISTRY["traces"].append(scenario)
```
