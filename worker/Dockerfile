# Production Dockerfile for Buun Curator Backend (Temporal Worker)
# syntax=docker.io/docker/dockerfile:1
#
# Uses official Playwright Python image which includes:
# - Python 3.12 (Ubuntu Noble)
# - Playwright browsers pre-installed at /ms-playwright
# - All browser dependencies

FROM mcr.microsoft.com/playwright/python:v1.57.0-noble AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Build stage
FROM base AS builder
WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock README.md ./

# Install dependencies (creates .venv in /app)
RUN uv sync --frozen --no-dev

# Copy application code
COPY buun_curator/ ./buun_curator/
COPY scripts/ ./scripts/

# Production stage
FROM base AS runner
WORKDIR /app

# Use existing pwuser (UID/GID 1001) from Playwright base image

# Copy virtual environment and application from builder
COPY --from=builder --chown=pwuser:pwuser /app/.venv ./.venv
COPY --from=builder --chown=pwuser:pwuser /app/buun_curator ./buun_curator
COPY --from=builder --chown=pwuser:pwuser /app/scripts ./scripts
COPY --from=builder --chown=pwuser:pwuser /app/pyproject.toml /app/uv.lock ./

USER pwuser

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Default command: start the Temporal worker
ENTRYPOINT ["python", "-m", "buun_curator.worker"]
