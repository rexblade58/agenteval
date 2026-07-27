# Human-in-the-loop review

Automatic checkers can be wrong — a code answer with the right logic but
different wording, a summary that misses a nuance. The review workflow lets
a human audit failed tasks and re-score the report without re-running the
model.

## Workflow

### 1. Generate a review queue

```bash
agenteval run --provider openai --model gpt-4o-mini --suite all \
  --review review.jsonl
```

This writes one entry per **failed task** — the prompt, the reference
answer, and the model's actual output — plus report metadata.

### 2. Judge the failures

```bash
agenteval review review.jsonl --interactive
```

For each task, answer `p` (pass), `f` (fail), or `s` (skip):

- **pass** — the checker was wrong; the answer is acceptable
- **fail** — the answer is genuinely wrong (keeps the failure)
- **skip** — the task is not applicable; it is removed from the totals

Or edit the queue file directly (JSONL — set `"status"` to `"pass"`,
`"fail"`, or `"skip"` on each line). Check progress any time with
`agenteval review review.jsonl`.

### 3. Apply the judgments

```bash
agenteval review review.jsonl --apply
```

Prints the re-scored report as JSON: adjusted `passed`, `total_tasks`,
`accuracy`, plus a `judgments` array and the count of skipped tasks.
The exit code is `0` if the re-scored accuracy is >= 50%, else `2`.

## Queue file format

The queue is JSONL: one metadata line, then one line per failed task.

```json
{"meta": {"provider": "openai", "model": "gpt-4o-mini", "suite": "all", "total_tasks": 16, "passed": 11}}
{"task_id": "qa-capital", "category": "qa", "prompt": "What is the capital of France?", "reference": "Paris", "output": "The capital is Berlin.", "status": "pending"}
```

## CI usage

Re-score inside a workflow when a run fails:

```yaml
- name: Evaluate
  run: agenteval run --provider openai --suite all --review review.jsonl || true
- name: Human review
  run: agenteval review review.jsonl --interactive --yes
- name: Gate
  run: agenteval review review.jsonl --apply | python -c "import json,sys; r=json.load(sys.stdin); sys.exit(0 if r['accuracy']>=0.7 else 1)"
```
