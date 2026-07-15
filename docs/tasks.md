# Tasks

AgentEval ships with task suites for the capabilities most teams care about.
Each task has a prompt, a reference answer (or automated checker), a
difficulty, and tags.

## Built-in suites

| Suite | Tasks | What it measures |
| :--- | :--- | :--- |
| `codegen` | FizzBuzz, Two Sum, Merge lists | Code correctness |
| `qa` | Capitals, concurrency | Knowledge recall |
| `reasoning` | Riddle, water jug | Step-by-step logic |
| `summarization` | Earnings, version control | Compression fidelity |
| `tool-use` | Date format, JSON parse | Function-calling ability |

## Custom tasks

Tasks are plain data. Add a custom task programmatically:

```python
from agenteval.tasks import Task
from agenteval.evaluator import Evaluator

task = Task(
    id="my-qa-1",
    category="qa",
    prompt="What is the tallest mountain on Earth?",
    reference="Everest",
    difficulty="easy",
    tags=["geography"],
)

evaluator = Evaluator(provider, suite="all")
# Extend the registry at runtime:
from agenteval.tasks import TASK_REGISTRY
TASK_REGISTRY["all"] = TASK_REGISTRY["all"] + [task]
```

Or write custom checkers:

```python
def semantic_check(output: str, reference: str) -> bool:
    # e.g., call an LLM judge, or use fuzzy matching
    return "everest" in output.lower()

task = Task(
    id="qa-everest",
    category="qa",
    prompt="What is the tallest mountain on Earth?",
    reference="Everest",
    checker=semantic_check,
)
```

## Checkers

| Checker | Behavior |
| :--- | :--- |
| default | `reference` in output (case-insensitive substring) |
| `contains_any` | Any of `ref\|alt1\|alt2` appears |
| `has_code_blocks` | Output contains code markers |
| `is_reasonable_length` | Output is longer than 20 chars |
| custom | Your own `(output, reference) -> bool` |
