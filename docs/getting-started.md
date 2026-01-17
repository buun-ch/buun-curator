# Getting Started

## Recommended: Kubernetes Installation

Local setup requires running multiple services (PostgreSQL, Temporal, Meilisearch) and is
complex to configure correctly. **We recommend using Helm to deploy on Kubernetes** for
production and development environments.

See [Helm Chart](../charts/buun-curator/README.md) for Kubernetes deployment instructions.

The rest of this document covers manual local setup for advanced users or development
without Kubernetes.

---

## Prerequisites

### Required Software

- [Bun](https://bun.sh/) >= 1.0 (recommend using [mise](https://mise.jdx.dev/))
- [Python](https://www.python.org/) >= 3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### External Services

- [PostgreSQL](https://www.postgresql.org/) >= 15 with [pgvector](https://github.com/pgvector/pgvector)
- [Temporal Server](https://temporal.io/)
- [Meilisearch](https://www.meilisearch.com/)
- OpenAI API key (or compatible LLM endpoint)

### Optional Services

- [Keycloak](https://www.keycloak.org/) - Authentication via [Better Auth](https://www.better-auth.com)
- [Langfuse](https://langfuse.com/) - LLM observability (required for AI evaluation)
- S3-compatible storage - For thumbnail storage (MinIO, AWS S3)

## External Services Setup

### PostgreSQL with pgvector

Install PostgreSQL and the pgvector extension:

```bash
# macOS (Homebrew)
brew install postgresql@15 pgvector

# Ubuntu/Debian
sudo apt install postgresql-15 postgresql-15-pgvector
```

Create the database and enable pgvector:

```sql
CREATE DATABASE buun_curator;
\c buun_curator
CREATE EXTENSION IF NOT EXISTS vector;
```

### Temporal Server

The easiest way to run Temporal locally is with the CLI:

```bash
# Install Temporal CLI
# macOS
brew install temporal

# Or download from https://github.com/temporalio/cli/releases

# Start Temporal dev server (includes Web UI at http://localhost:8233)
temporal server start-dev --namespace default
```

For production, see [Temporal Server deployment](https://docs.temporal.io/self-hosted-guide).

### Meilisearch

```bash
# macOS
brew install meilisearch

# Start Meilisearch
meilisearch --master-key="your-master-key"

# Or with Docker
docker run -d -p 7700:7700 \
  -e MEILI_MASTER_KEY="your-master-key" \
  -v $(pwd)/meili_data:/meili_data \
  getmeili/meilisearch:latest
```

Meilisearch will be available at `http://localhost:7700`.

## Application Setup

### 1. Clone and Install Dependencies

```bash
git clone https://github.com/your-org/buun-curator.git
cd buun-curator

# Install dependencies
bun install

# Install Python dependencies for worker
cd worker
uv sync
playwright install  # Required for Crawl4AI
cd ..

# Install Python dependencies for agent
cd agent
uv sync
cd ..
```

### 2. Configure Environment Variables

Copy example environment files:

```bash
cp .env.example .env
cp worker/.env.example worker/.env
cp agent/.env.example agent/.env
```

Edit each `.env` file with your configuration.

#### Root `.env` (Next.js App)

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/buun_curator

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_MODEL=gpt-4o

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=buun-curator

# Meilisearch
MEILISEARCH_HOST=http://localhost:7700
MEILISEARCH_INDEX=buun-curator
# MEILISEARCH_API_KEY=your-master-key

# Agent
AGENT_URL=http://localhost:8000
```

#### `worker/.env`

```bash
# API Connection
BUUN_CURATOR_API_URL=http://localhost:3000

# Database (worker needs direct DB access)
DATABASE_URL=postgresql://user:password@localhost:5432/buun_curator

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=buun-curator

# OpenAI
OPENAI_API_KEY=sk-xxx
LLM_MODEL=gpt-4o

# Meilisearch
MEILISEARCH_HOST=http://localhost:7700
MEILISEARCH_INDEX=buun-curator
```

#### `agent/.env`

```bash
# Server
HOST=0.0.0.0
PORT=8000

# API Connection
API_BASE_URL=http://localhost:3000

# OpenAI
OPENAI_API_KEY=sk-xxx
RESEARCH_MODEL=gpt-4o

# Temporal
TEMPORAL_HOST=localhost:7233
TEMPORAL_NAMESPACE=default
TEMPORAL_TASK_QUEUE=buun-curator
```

### 3. Run Database Migrations

```bash
bun db:migrate
```

### 4. Initialize Meilisearch Index

After starting the worker (step 5), initialize the search index:

```bash
cd worker
uv run trigger reindex
```

## Running the Application

You need to run three processes. Use separate terminal windows or a process manager
like [overmind](https://github.com/DarthSim/overmind).

### Terminal 1: Next.js App

```bash
bun dev
```

The app will be available at `http://localhost:3000`.

### Terminal 2: Python Worker

```bash
cd worker
uv run worker

# Or with auto-reload for development
uv run worker --reload
```

### Terminal 3: AI Agent

```bash
cd agent
uv run agent

# Or with auto-reload for development
LOG_LEVEL=debug RELOAD=true uv run agent
```

## Verify Installation

1. Open `http://localhost:3000` in your browser
1. Add a feed subscription in the settings
1. Trigger feed ingestion: `cd worker && uv run trigger ingest`
1. Check Temporal Web UI at `http://localhost:8233` to monitor workflows

## Using 1Password for Secrets (Optional)

If you use 1Password, create `.env.op` files with secret references:

```bash
# .env.op
OPENAI_API_KEY="op://Vault/openai/api-key"
DATABASE_URL="op://Vault/postgres/connection-string"
```

Run commands with secret injection:

```bash
op run --env-file=.env.op -- bun dev
op run --env-file=worker/.env.op -- uv run worker
```

## Troubleshooting

### Worker cannot connect to Temporal

Ensure Temporal server is running:

```bash
temporal server start-dev --namespace default
```

Check `TEMPORAL_HOST` in worker/.env matches your Temporal server address.

### Meilisearch search not working

1. Verify Meilisearch is running: `curl http://localhost:7700/health`
2. Check `MEILISEARCH_HOST` and `MEILISEARCH_API_KEY` in both `.env` and `worker/.env`
3. Rebuild the index: `cd worker && uv run trigger reindex`

### Database connection errors

1. Verify PostgreSQL is running
2. Check pgvector extension is installed: `SELECT * FROM pg_extension WHERE extname = 'vector';`
3. Verify `DATABASE_URL` format: `postgresql://user:password@host:port/database`

### Agent not responding

1. Check agent is running on port 8000
2. Verify `AGENT_URL` in root `.env` points to the agent
3. Check agent logs for errors
