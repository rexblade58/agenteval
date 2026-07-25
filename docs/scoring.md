# Scoring

AgentEval reports three classes of metrics:

## Accuracy

The primary score — the fraction of tasks where the agent's output passed
the task checker.

```
accuracy = passed_tasks / total_tasks
```

## Robustness

When the `adversarial` suite is included (via `--suite adversarial` or
`--suite all`), reports also carry a **robustness** score — the accuracy on
adversarial tasks only (prompt injection, jailbreak, hallucination bait):

```
robustness = passed_adversarial_tasks / total_adversarial_tasks
```

It appears in the JSON report as `robustness` and in Markdown reports as a
dedicated line. A high accuracy with low robustness means an agent answers
well but is easily steered or hallucinates — exactly the gap this metric
exists to expose.

## Scoring modes

Two task-scoring modes are available via `--scoring`:

| Mode | Default | How it works |
| :--- | :--- | :--- |
| `contains` | ✅ | Reference answer must appear as a substring (case-insensitive). Fast, strict, zero dependencies. |
| `semantic` | | Token overlap scoring: for short references (1-2 content words) the answer must be fully covered; for longer references a Jaccard similarity over stopword-stripped tokens must meet a threshold. |

Semantic mode is robust to paraphrase — `"Paris serves as the capital city of
France"` passes against the reference `"The capital of France is Paris."`
even though substring matching would fail:

```bash
agenteval run --provider openai --model gpt-4o-mini --suite qa --scoring semantic
```

The active scoring mode is recorded in the report's `raw.scoring` field.
It has no effect on tasks with custom checkers.

## pass@k

For `--n-samples k`, each task is run `k` times and counts as passed if **any**
sample succeeds. This is the standard way to measure sampling robustness —
same as `pass@k` in code-generation research.

## Cost & latency

Every provider returns token usage and cost, so you can compare:

- **Cost per 100 runs** — important when comparing `gpt-4o-mini` vs `claude-3-5`
- **Average latency** — important for production agents

The report includes a category breakdown so you can see if an agent is great
at QA but weak at code generation:

```text
| Category | Passed | Total | Accuracy |
|----------|--------|-------|----------|
| codegen  | 3      | 3     | 100.0%   |
| qa       | 1      | 2     | 50.0%    |
| reasoning| 2      | 2     | 100.0%   |
```

## CI thresholds

The CLI exits with:

- `0` — accuracy >= 50%
- `2` — accuracy < 50%

Use JSON output in CI to gate on any threshold you choose.
