# GitHub Actions integration

AgentEval ships a reusable GitHub Actions workflow so any repository can
gate on agent quality without writing CI from scratch.

## Quick start

Copy `examples/agent-eval-workflow.yml` into your repository at
`.github/workflows/agent-eval.yml` and add the API key secrets you need.

```yaml
on:
  push:
    branches: [main]

jobs:
  evaluate:
    uses: rexblade58/agenteval/.github/workflows/eval.yml@main
    with:
      provider: openai
      model: gpt-4o-mini
      suite: all
      min-accuracy: 0.7
    secrets:
      OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

The workflow installs AgentEval from this repository, runs the evaluation,
fails the job when accuracy falls below `min-accuracy`, and uploads the JSON
report as an artifact named `agenteval-report`.

## Inputs

| Input | Default | Description |
| :--- | :--- | :--- |
| `provider` | `mock` | `mock`, `openai`, `anthropic`, `gemini`, `groq`, `ollama` |
| `model` | *(provider default)* | Model identifier |
| `suite` | `all` | `codegen`, `qa`, `reasoning`, `summarization`, `tool-use`, `all` |
| `scoring` | `contains` | `contains` or `semantic` |
| `n-samples` | `1` | Samples per task (pass@k) |
| `min-accuracy` | `0.7` | Fail the workflow below this accuracy (0..1) |
| `agenteval-ref` | `main` | Git ref of AgentEval to install (pin a tag for stability) |
| `python-version` | `3.11` | Python version for the runner |

## Secrets

Pass through only the secrets your provider needs: `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`.

## Pinning

For production pipelines pin `agenteval-ref` to a release tag or commit SHA
so evaluation results stay reproducible:

```yaml
uses: rexblade58/agenteval/.github/workflows/eval.yml@v1
```

## Weekly regression example

```yaml
on:
  schedule:
    - cron: "0 6 * * 1" # Monday 06:00 UTC

jobs:
  evaluate:
    uses: rexblade58/agenteval/.github/workflows/eval.yml@v1
    with:
      provider: mock
      suite: all
      min-accuracy: 1.0
```
