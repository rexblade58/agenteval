# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Builder stage: install AgentEval into a virtualenv
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

COPY packages/core/ ./packages/core/

RUN python -m venv /opt/agenteval && \
    /opt/agenteval/bin/pip install --upgrade pip && \
    /opt/agenteval/bin/pip install ./packages/core

# ---------------------------------------------------------------------------
# Runtime stage: minimal image with the CLI + dashboard
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

ENV PATH="/opt/agenteval/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    AGENTEVAL_REPORTS_DIR=/data/reports

WORKDIR /data

COPY --from=builder /opt/agenteval /opt/agenteval

# Reports directory for the dashboard; writable by the default user
RUN mkdir -p /data/reports && \
    addgroup --system --gid 10001 agenteval && \
    adduser --system --uid 10001 --ingroup agenteval agenteval && \
    chown -R agenteval:agenteval /data

USER agenteval

EXPOSE 8000

VOLUME ["/data/reports"]

# Default command: start the web dashboard
CMD ["agenteval", "serve", "--dir", "/data/reports", "--host", "0.0.0.0", "--port", "8000"]
