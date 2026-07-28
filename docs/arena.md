# Arena — battle coding agents on real tasks

> **Make AI agents prove their code works.**

Arena runs multiple autonomous coding agents against the **same real
repository task**, lets each one work in an isolated git worktree, verifies
the results with real test/build/lint commands, detects regressions, and
ranks who actually solved it.

```bash
agenteval arena \
  --repo . \
  --task "fix the checkout discount calculation" \
  --agents codex,claude,opencode
```

```text
Agent        Tests    Build   Regression   Cost     Time    Score
─────────────────────────────────────────────────────────────────
Codex        47/47    PASS    0            $0.31    4m12s   96
Claude       47/47    PASS    1            $0.48    3m51s   92
OpenCode     39/42    FAIL    3            $0.08    5m03s   71

🏆 Winner: Codex
```

## How it works

1. **Baseline** — the untouched repository (at a fixed commit) is verified
   first: tests, build, lint, typecheck. These results define the starting
   point for regression detection.
2. **Isolation** — each agent gets its own detached git worktree at the
   exact same starting commit. The original repository is never modified.
3. **Run** — every agent receives the identical task and environment, with
   a configurable timeout.
4. **Verify** — each modified workspace is verified with real commands.
5. **Regression** — agent results are compared against the baseline: tests
   fixed, new failures introduced, build/lint/typecheck regressions.
6. **Score** — transparent weighted scoring where functional correctness
   (real passing tests) dominates. An LLM judge can never override a
   failed test.
7. **Rank** — results are ranked and exported to JSON/Markdown/HTML under
   `.agenteval/runs/<timestamp>/`.

## Quick start

```bash
# check your environment
agenteval doctor

# see available adapters
agenteval agents list

# battle two agents on the current repo
agenteval arena \
  --repo . \
  --task "fix the failing checkout test" \
  --agents codex,claude
```

Remote repositories work too — they are cloned once and worktrees are
created from the clone:

```bash
agenteval arena \
  --repo https://github.com/octocat/Hello-World \
  --task "add a CONTRIBUTING guide" \
  --agents codex,claude
```

## Agents

| Name | Adapter | Command used |
| :--- | :--- | :--- |
| `codex` | OpenAI Codex CLI | `codex exec --skip-git-repo-check --sandbox workspace-write {task}` |
| `claude` | Claude Code | `claude -p --dangerously-skip-permissions {task}` |
| `gemini` | Gemini CLI | `gemini -p {task}` |
| `opencode` | OpenCode | `opencode run {task}` |
| `aider` | Aider | `aider --message {task} --yes-always` |
| `command` | Generic | any command with `{task}`/`{workspace}` placeholders |

### Custom agents via agenteval.yaml

Add any executable as an agent without touching the codebase:

```yaml
# agenteval.yaml
agents:
  my-agent:
    command: my-agent run "{task}"
    timeout: 900
    shell: false
    description: My custom agent
```

## Verification

Verification runs real commands in the modified workspace:

| Verifier | What runs (auto-detected) |
| :--- | :--- |
| `tests` | `npm test` / `pytest` / `cargo test` / `go test ./...` / `mvn test` / `composer test` / `flutter test` |
| `build` | `npm run build` / `cargo check` / `mvn package` / `gradle build` |
| `lint` | `npm run lint` / `ruff check .` / `cargo clippy` / `go vet ./...` / `flutter analyze` |
| `typecheck` | `npx tsc --noEmit` / `mypy .` |

Detection is based on manifest files (`package.json`, `pyproject.toml`,
`Cargo.toml`, `go.mod`, `pom.xml`, `build.gradle`, `composer.json`,
`pubspec.yaml`, ...). Override with explicit config:

```yaml
# agenteval.yaml
verification:
  verify:
    tests:
      - python -m pytest -x
      - python -m pytest tests/integration
    build:
      - python -m build

project:
  language: python
  install: pip install -e .[dev]
  test: [python -m pytest]
```

Every command's exit code, duration, stdout, and stderr are recorded in
the report. All inferred commands are visible — nothing runs silently.

## Regression detection

An agent does not win by fixing one test while breaking others. The
baseline is compared against each modified workspace:

- tests fixed vs new failures introduced
- build / lint / typecheck regressions (passing before, failing after)

New regressions are penalized heavily in scoring.

## Scoring

Default weights (configurable via `scoring:` in agenteval.yaml):

| Dimension | Weight | What it measures |
| :--- | :--- | :--- |
| functional | 50% | Real tests passing in the modified workspace |
| regression | 20% | No new failures vs baseline |
| build | 10% | Build/check passes |
| quality | 10% | Lint + typecheck |
| cost | 5% | Cheapest attempt scores highest |
| speed | 5% | Fastest attempt scores highest |

Hard rule: **if tests fail, that is reflected in the score** — no LLM
judge can override it. Agent outcomes use explicit states, never a bare
number:

```
PASS  PARTIAL  FAIL  TIMEOUT  AGENT_ERROR  ENVIRONMENT_ERROR  VERIFICATION_ERROR  CANCELLED
```

## Results & artifacts

Every run writes to `.agenteval/runs/<timestamp>/`:

```
report.json    portable machine-readable result (schema v1)
report.md      human-readable comparison
report.html    shareable report
```

```bash
agenteval arena --repo . --task "..." --agents codex,claude --format json
agenteval arena --repo . --task "..." --agents codex,claude --format html
```

The JSON schema is stable and includes full reproducibility metadata:
commit, dirty state, environment, agent commands, verification commands,
timeouts, and scoring weights.

## Security

Running autonomous coding agents executes **untrusted code on your
machine**. Mitigations built in:

- isolated git worktrees (the source repo is never checked out/modified)
- hard per-command and per-agent timeouts with process-tree kill
- bounded stdout/stderr capture (512 KB per command)
- no secrets are ever displayed (`agenteval doctor` reports availability only)

Docker/container isolation and network restrictions are planned hardening.
Treat shell-running agents as unsafe by default.

## Options

```text
--repo PATH|URL     repository (default .)
--task TEXT|FILE    task description or path to a task file
--agents LIST       comma-separated agent names
--runs N            attempts per agent
--parallel          run agents concurrently
--timeout S         per-agent timeout (default 900)
--commit SHA        starting commit (default HEAD)
--verifiers LIST    tests,build,lint,typecheck
--format FMT        json | markdown | html
--output-dir DIR    artifact directory
--keep-worktrees    keep worktrees for inspection
```
