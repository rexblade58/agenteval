# Benchmark packs

A benchmark pack bundles a **repository + a sequence of tasks** into a
named, reproducible benchmark that can be run against any installed
agents. Packs are how teams publish reusable evaluations.

## Quick start

```bash
# list installed packs
agenteval benchmark list

# install from a git URL or a local directory
agenteval benchmark install https://github.com/your-org/your-benchmark
agenteval benchmark install ./my-pack

# run a pack against its default agents
agenteval benchmark run discount-checkout

# or override agents
agenteval benchmark run discount-checkout --agents codex,claude
```

## Pack layout

```text
my-pack/
├── agenteval-benchmark.yaml   # manifest (required)
├── agenteval.yaml             # optional: custom agents/verifiers for this pack
└── repo/                      # optional: local fixture repository
```

## Manifest reference

```yaml
# agenteval-benchmark.yaml
name: discount-checkout          # required, unique
description: Fix the checkout discount threshold
repo: https://github.com/user/project   # git URL or local path
commit: main                     # optional starting ref/commit
tasks:                           # required, at least one
  - "Fix the checkout discount: 10% off over $50"
  - "Ensure discounts work with multiple products"
agents: [codex, claude]          # default agents for this pack
runs: 1                          # attempts per task
timeout: 900                     # per-agent timeout in seconds
parallel: false
```

A pack's `repo` may point to a git URL (cloned fresh per run) or a local
path relative to the pack directory.

## Built-in packs

The repository ships an example pack in `benchmarks/`:

| Pack | Repo | Tasks |
| :--- | :--- | :--- |
| `discount-checkout` | `rexblade58/agenteval-fixtures` (python-app) | Fix the checkout discount |

## Authoring guide

1. Create a directory with `agenteval-benchmark.yaml`
2. Point `repo` at a fixture repository with **failing tests** that agents
   must fix — that's what makes the benchmark measurable
3. Write tasks as concrete instructions an agent can act on
4. Optionally include `agenteval.yaml` with custom agents (see Arena docs)
5. Test locally: `agenteval benchmark run <name> --dir .`
6. Publish the pack directory as a git repository so others can
   `agenteval benchmark install <url>`

## Fairness

Every task in a pack runs each agent from the same starting commit with
the same environment, verification, and timeout. Scores are only
comparable within a pack (and ideally the same machine) until the
[opt-in leaderboard](https://github.com/rexblade58/agenteval/issues/13)
normalizes across environments.
