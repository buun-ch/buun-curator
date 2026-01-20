# Buun Curator Worker

Temporal-based worker for Buun Curator feed reader.

## Features

- **AllFeedsIngestionWorkflow**: Parent workflow that orchestrates all feed ingestion using child workflows
- **SingleFeedIngestionWorkflow**: Process individual feed (crawl → fetch → summarize)
- **ReprocessEntriesWorkflow**: Reprocess existing entries (fetch + summarize)
- **ContentProcessingWorkflow**: Standalone content processing for batch filtering and summarization
- **SearchReindexWorkflow**: Rebuild Meilisearch full-text search index
- **Temporal-powered**: Durable execution, automatic retries, observability

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Temporal Server (local or cloud)
- Buun Curator Next.js server (REST API)
- Playwright browsers (for Crawl4AI)

## Setup

```bash
cd worker

# Install dependencies
uv sync

# Install Playwright browsers (required for Crawl4AI)
playwright install

# Copy environment template
cp .env.example .env
```

## Configuration

Edit `.env` to configure:

```bash
# Buun Curator REST API URL
BUUN_CURATOR_API_URL="http://localhost:3000"

# Temporal
TEMPORAL_HOST="localhost:7233"
TEMPORAL_NAMESPACE="buun-curator"  # Must match your Temporal namespace
TEMPORAL_TASK_QUEUE="buun-curator"

# Meilisearch (full-text search)
MEILISEARCH_HOST="localhost:7700"
MEILISEARCH_API_KEY="your-master-key"
MEILISEARCH_INDEX="buun-curator"  # Index name (default: buun-curator)

# OpenAI (for summarization)
OPENAI_API_KEY="sk-xxxxxx"
# OPENAI_BASE_URL="http://litellm.litellm:4000"  # Optional: LiteLLM proxy URL

# Feature flags
ENABLE_CONTENT_FETCH=true
ENABLE_SUMMARIZATION=true

# Content filtering mode
# "hybrid" (default): PruningContentFilter with fallback to raw markdown
# "rules": Rule-based only (excluded_tags + CSS selectors)
CONTENT_FILTER_MODE=hybrid

# Concurrency settings
FEED_INGESTION_CONCURRENCY=5  # Max concurrent child workflows for feed ingestion
FETCH_CONCURRENCY=3           # Max concurrent HTTP fetch requests per activity
```

If you use 1Password for secrets management, create a `.env.op` file:

```bash
OPENAI_API_KEY="op://Personal/openai-key/credential"
```

## Usage

Note: `.env` is not automatically loaded. Load environment variables before running commands:

```bash
# Load .env
source .env

# Or use 1Password CLI for secrets injection
op run --env-file=.env.op -- <command>
```

### Start the Worker

```bash
# Start Temporal worker
uv run worker

# Start with auto-reload (restarts on file changes)
uv run worker --reload

# Or via module
uv run python -m buun_curator.worker
```

The `--reload` flag enables hot reload for development. When enabled, the worker
automatically restarts when Python files change in these directories:

### Trigger Workflows

```bash
# Run full feed ingestion (crawl + fetch + summarize)
# Uses child workflows for parallel processing with configurable concurrency
uv run trigger ingest

# Run without summarization
uv run trigger ingest --no-summarize

# Run without content fetch
uv run trigger ingest --no-fetch
```

#### Single Feed Ingestion

```bash
# List all feeds (shows feed IDs, names, URLs)
uv run trigger list-feeds

# Ingest a specific feed by ID
uv run trigger ingest-feed FEED_ID

# Ingest specific feed without summarization
uv run trigger ingest-feed FEED_ID --no-summarize

# Ingest specific feed without content fetch
uv run trigger ingest-feed FEED_ID --no-fetch
```

#### Reprocess Specific Entries

```bash
# Reprocess specific entries by ID (fetch + summarize)
uv run trigger reprocess ENTRY_ID1 ENTRY_ID2

# Reprocess specific entries - fetch only (no summarization)
uv run trigger reprocess ENTRY_ID1 --no-summarize

# Reprocess specific entries - summarize only (no fetch)
uv run trigger reprocess ENTRY_ID1 --no-fetch
```

#### Summarization

```bash
# Summarize all unsummarized entries (that have content but no summary)
uv run trigger summarize

# Summarize specific entries
uv run trigger summarize --entry-ids ID1 ID2 ID3

# Custom batch size
uv run trigger summarize --batch-size 10
```

#### Debug Commands

```bash
# Fetch content for debugging (direct, without Temporal)
uv run trigger fetch ENTRY_ID

# Fetch content from URL directly
uv run trigger fetch --url URL --title "Entry Title"

# Fetch and save to API
uv run trigger fetch ENTRY_ID --save
```

#### Search Index

```bash
# Rebuild full-text search index (Meilisearch)
uv run trigger reindex

# Rebuild with custom batch size
uv run trigger reindex --batch-size 200
```

**Note**: The reindex workflow fetches all entries using cursor-based pagination
and indexes them in batches. This is useful for initial setup or resyncing
after Meilisearch data loss.

**Note**: `ingest` workflow has `auto_summarize=True` by default, so it will automatically
summarize new entries after fetching content. The `summarize` command is useful for:

- Re-running summarization on entries that failed
- Summarizing specific entries by ID
- Batch processing entries that were ingested with `--no-summarize`

### Schedule

Manage periodic execution of the ingest workflow using Temporal Schedules:

```bash
# Show current schedule status
uv run schedule show

# Set schedule with interval (e.g., every 6 hours)
uv run schedule set --interval 6h

# Set schedule to run daily at 6:00 and 18:00
uv run schedule set --cron "0 6,18 * * *"

# Set schedule to run every 30 minutes between 8:00 and 23:30 daily
uv run schedule set --cron "0,30 8-23 * * *"

# Set schedule with options
uv run schedule set --interval 6h --no-summarize
uv run schedule set --interval 6h --no-fetch

# Pause/resume schedule
uv run schedule pause
uv run schedule resume

# Trigger immediately (without waiting for next scheduled time)
uv run schedule trigger

# Delete schedule
uv run schedule delete
```

**Interval format:**

| Format | Duration   |
| ------ | ---------- |
| `30m`  | 30 minutes |
| `6h`   | 6 hours    |
| `1d`   | 1 day      |

## Development

```bash
# Type checking
uv run pyright

# Linting
uv run ruff check .

# Format
uv run ruff format .
```

## Documentation

For implementation details (directory structure, workflows, activity patterns, testing), see [../docs/implementation.md](../docs/implementation.md#worker-temporal).

## Future Plans

- **DeepResearchWorkflow**: Multi-agent research using LangGraph
- **Knowledge Graph**: Entity extraction and graph construction
