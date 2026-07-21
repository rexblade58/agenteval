# Getting Started with AgentEval

## Installation

### Python core

```bash
pip install -e packages/core
```

Or from PyPI (once published):

```bash
pip install agenteval
```

### TypeScript SDK

```bash
npm install @agenteval/sdk
```

## Quick start

Run the mock provider (no API key needed):

```bash
agenteval run --provider mock --suite all
```

Evaluate a real model:

```bash
export OPENAI_API_KEY=sk-...
agenteval run --provider openai --model gpt-4o-mini --suite codegen
```

Anthropic:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
agenteval run --provider anthropic --model claude-3-5-sonnet-latest --suite qa
```

Local models (Ollama):

```bash
agenteval run --provider ollama --model llama3.2 --suite reasoning
```

## Output formats

JSON:

```bash
agenteval run --provider mock --format json
```

Write to a file:

```bash
agenteval run --provider openai --format markdown --output report.md
```

## Web dashboard

Save reports into a directory and serve them locally to see trends across
providers and time:

```bash
mkdir -p reports
agenteval run --provider mock --suite all --format json --output reports/mock.json
agenteval serve --dir reports
# open http://127.0.0.1:8000
```

The dashboard is dependency-free (Python stdlib only) and shows accuracy by
provider, an accuracy-over-time chart, and the full report table. The JSON API
is available at `/api/reports`.

## Using in CI

The CLI exits with code 2 when accuracy is below 50%, so you can gate
deployments on agent quality:

```yaml
- name: Evaluate agent
  run: agenteval run --provider openai --model gpt-4o-mini --suite all --format json --output eval.json
- name: Fail if below threshold
  run: |
    python -c "
    import json; r = json.load(open('eval.json'))
    assert r['accuracy'] >= 0.7, f'Accuracy {r[\"accuracy\"]} < 0.7'
    "
```

## Next steps

- [Providers](providers.md) — supported backends and how to add your own
- [Tasks](tasks.md) — built-in suites and custom tasks
- [Scoring](scoring.md) — how metrics are computed
