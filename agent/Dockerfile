# Production Dockerfile for Buun Agent (LangGraph-based AI agent service)
# syntax=docker.io/docker/dockerfile:1

FROM python:3.12-slim-bookworm AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Build stage
FROM base AS builder
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./

# Install dependencies (creates .venv in /app)
RUN uv sync --frozen --no-dev

# Copy application code
COPY buun_curator_agent/ ./buun_curator_agent/

# Production stage
FROM base AS runner
WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 agent && \
    useradd --uid 1000 --gid agent --shell /bin/bash --create-home agent

# Copy virtual environment and application from builder
COPY --from=builder --chown=agent:agent /app/.venv ./.venv
COPY --from=builder --chown=agent:agent /app/buun_curator_agent ./buun_curator_agent
COPY --from=builder --chown=agent:agent /app/pyproject.toml /app/uv.lock ./

USER agent

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Default command: start the agent service
ENTRYPOINT ["python", "-m", "buun_curator_agent.main"]
