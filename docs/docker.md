# Docker

AgentEval ships a multi-stage Docker image for running the CLI and the web
dashboard without a local Python toolchain. Images are published to
**GHCR** (`ghcr.io/rexblade58/agenteval`) for `linux/amd64` and `linux/arm64`
on every release tag and on pushes to `main`.

## Pull

```bash
docker pull ghcr.io/rexblade58/agenteval:latest
```

## Run the CLI

The image runs the dashboard by default; override the command for one-off
evaluations:

```bash
docker run --rm ghcr.io/rexblade58/agenteval:latest \
  agenteval list-providers
```

### Mock evaluation (no API key)

```bash
docker run --rm ghcr.io/rexblade58/agenteval:latest \
  agenteval run --provider mock --suite all
```

### Real provider

Pass the key via environment variable and persist the report:

```bash
docker run --rm \
  -e OPENAI_API_KEY=sk-... \
  -v "$PWD/reports:/data/reports" \
  ghcr.io/rexblade58/agenteval:latest \
  agenteval run --provider openai --model gpt-4o-mini --suite codegen \
  --format json --output /data/reports/codegen.json
```

## Run the dashboard

```bash
docker run --rm -d \
  -p 8000:8000 \
  -v "$PWD/reports:/data/reports" \
  --name agenteval \
  ghcr.io/rexblade58/agenteval:latest
# open http://localhost:8000
```

Reports written into `$PWD/reports` on the host are served by the dashboard
inside the container.

## Build locally

```bash
docker build -t agenteval .
docker run --rm agenteval agenteval list-providers
```

## Image details

- Base: `python:3.11-slim`
- Non-root user (`agenteval`, UID 10001), reports volume at `/data/reports`
- Multi-arch: `linux/amd64`, `linux/arm64`
- Publishing: `.github/workflows/docker-publish.yml` (tags `v*`, `latest` on main, SHA tags)
