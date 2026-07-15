# Scoring

AgentEval reports three classes of metrics:

## Accuracy

The primary score — the fraction of tasks where the agent's output passed
the task checker.

```
accuracy = passed_tasks / total_tasks
```

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
