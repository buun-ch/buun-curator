# CLI Reference

CLI command reference for Buun Curator services.

## Overview

Buun Curator provides CLI commands in two services:

**Agent Service (`agent/`):**

| Command | Description |
|---------|-------------|
| `agent` | Start FastAPI server |
| `agent-cli` | CLI for testing agents |
| `batch-eval` | RAGAS batch evaluation |

**Worker Service (`worker/`):**

| Command | Description |
|---------|-------------|
| `worker` | Start Temporal worker |
| `trigger` | Trigger workflows manually |
| `schedule` | Manage Temporal schedules |
| `fetch` | Debug content fetching |
| `generate-singlehop-eval-dataset` | Generate single-hop evaluation dataset (RAGAS) |
| `generate-multihop-eval-dataset` | Generate multi-hop evaluation dataset |
| `generate-filtering-dataset` | Generate filtering evaluation dataset |
| `run-filtering-on-dataset` | Run filtering on dataset |

Commands should be run from the respective directories:

```bash
cd agent && uv run <command>  # Agent commands
cd worker && uv run <command>  # Worker commands
```

---

## Agent Service

### agent

Start the FastAPI server. Used for CopilotKit integration.

```bash
uv run agent
```

Configuration can be changed via environment variables (see `agent/buun_curator_agent/config.py`).

### agent-cli

CLI for testing agents directly without going through the API.

#### Subcommands

```text
agent-cli
├── dialogue    # Run dialogue agent directly
├── research    # Run research agent directly
└── api         # Test API endpoints
```

#### dialogue

Run the dialogue agent directly (simple LLM chat).

```bash
agent-cli dialogue <message> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `message` | User message |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--context` | `-c` | Entry context (content) |

**Examples:**

```bash
uv run agent-cli dialogue "What is LangGraph?"
uv run agent-cli dialogue "Summarize this entry" --context "Entry content..."
```

#### research

Run the research agent directly (LangGraph workflow: Planner → Retriever → Writer).

```bash
agent-cli research <query> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `query` | Search query |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--mode` | `-m` | `planner` | Search mode |

**Search Modes:**

| Mode | Description |
|------|-------------|
| `planner` | Planner selects optimal sources based on query |
| `meilisearch` | Use Meilisearch (full-text search) only |
| `embedding` | Use embedding (vector search) only |
| `hybrid` | Use both and merge results |

**Examples:**

```bash
uv run agent-cli research "What is LangGraph?"
uv run agent-cli research "LangGraph tutorial" --mode meilisearch
uv run agent-cli research "How do AI agents work?" --mode embedding
uv run agent-cli research "RAG best practices" --mode hybrid
```

#### api

Test API endpoints.

```bash
agent-cli api [options] <subcommand>
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--base-url` | `-u` | `http://buun-curator-agent.buun-curator:8000` | Agent service URL |

**Subcommands:**

- `chat <message>` - Test `/chat` endpoint (`--stream` for streaming)
- `health` - Test `/health` endpoint

**Examples:**

```bash
uv run agent-cli api chat "Hello"
uv run agent-cli api chat "Hello" --stream
uv run agent-cli api health
uv run agent-cli api -u http://localhost:8000 health
```

### batch-eval

Run RAGAS batch evaluation using a Langfuse Dataset.

```bash
batch-eval [options]
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--dataset-name` | | `research-evaluation` | Langfuse dataset name |
| `--run-name` | | Auto-generated | Name for this evaluation run |
| `--limit` | | None | Maximum number of items to evaluate |
| `--dry-run` | | | Print items without running evaluation |
| `--verbose` | `-v` | | Enable verbose logging |
| `--no-save` | | | Skip saving results to file |
| `--mode` | `-m` | `planner` | Search mode |
| `--all-modes` | | | Run evaluation for all search modes sequentially |

**Examples:**

```bash
uv run batch-eval
uv run batch-eval --dataset-name my-dataset
uv run batch-eval --limit 5
uv run batch-eval --dry-run
uv run batch-eval --mode embedding
uv run batch-eval --all-modes
```

**Output:**

Results are saved to:

```text
../worker/evaluation/<dataset-name>/results/<date>-<mode>-<seq>.json
```

---

## Worker Service

### worker

Start the Temporal worker.

```bash
uv run worker [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--reload` | Enable auto-reload on file changes |

**Examples:**

```bash
uv run worker
uv run worker --reload
op run --env-file=.env.op -- uv run worker
```

### trigger

Trigger Buun Curator workflows manually.

```bash
trigger <subcommand> [options]
```

#### Subcommands

| Subcommand | Description |
|------------|-------------|
| `ingest` | Run feed ingestion workflow for all feeds |
| `ingest-feed` | Run ingestion workflow for a single feed |
| `list-feeds` | List all registered feeds |
| `distill-entries` | Run entry distillation workflow |
| `reprocess` | Reprocess specific entry IDs (fetch + summarize) |
| `fetch` | Fetch content for debugging |
| `extract-context` | Extract structured context from an entry |
| `collect-context` | Collect context from multiple entries and analyze |
| `reindex` | Rebuild search index (Meilisearch) |
| `prune` | Remove orphaned documents from search index |
| `deep-research` | Run deep research on an entry with a query |
| `graph-rebuild` | Rebuild global knowledge graph |
| `graph-update` | Add pending entries to knowledge graph |
| `cleanup` | Delete old entries (read, unstarred, not upvoted) |
| `embedding-backfill` | Compute embeddings for entries without them |

#### trigger ingest

Run feed ingestion workflow for all feeds.

```bash
trigger ingest [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `--no-summarize` | Skip automatic summarization |
| `--no-fetch` | Skip content fetching |

**Examples:**

```bash
uv run trigger ingest
uv run trigger ingest --no-summarize
uv run trigger ingest --no-fetch
```

#### trigger ingest-feed

Run ingestion workflow for a single feed.

```bash
trigger ingest-feed <feed_id> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `feed_id` | Feed ID to ingest |

**Options:**

| Option | Description |
|--------|-------------|
| `--no-summarize` | Skip automatic summarization |
| `--no-fetch` | Skip content fetching |

**Examples:**

```bash
uv run trigger ingest-feed 01ABC123DEF456
uv run trigger ingest-feed 01ABC123DEF456 --no-summarize
```

#### trigger deep-research

Run deep research on an entry with a query.

```bash
trigger deep-research <entry_id> <query>
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `entry_id` | Entry ID to research |
| `query` | Research query |

**Examples:**

```bash
uv run trigger deep-research 01ABC123DEF456 "What are the key points?"
```

#### Other trigger subcommands

```bash
uv run trigger list-feeds
uv run trigger distill-entries
uv run trigger reindex
uv run trigger prune
uv run trigger graph-rebuild
uv run trigger graph-update
uv run trigger cleanup
uv run trigger embedding-backfill
```

### schedule

Manage Temporal schedules for Buun Curator.

```bash
schedule <subcommand> [options]
```

#### Subcommands

| Subcommand | Description |
|------------|-------------|
| `show` | Show current schedule status |
| `set` | Create or update schedule |
| `pause` | Pause the schedule |
| `resume` | Resume the schedule |
| `delete` | Delete the schedule |
| `trigger` | Trigger the schedule immediately |
| `graph` | Manage graph update schedule |
| `cleanup` | Manage entries cleanup schedule |

**Examples:**

```bash
uv run schedule show
uv run schedule set
uv run schedule pause
uv run schedule resume
uv run schedule trigger
uv run schedule graph show
uv run schedule cleanup show
```

### fetch

Fetch entry content using ContentFetcher (for debugging).

```bash
fetch <url> [options]
```

**Arguments:**

| Argument | Description |
|----------|-------------|
| `url` | URL to fetch |

**Options:**

| Option | Short | Description |
|--------|-------|-------------|
| `--title` | `-t` | Entry title (for duplicate heading removal) |
| `--screenshot` | `-s` | Capture screenshot |
| `--exclude` | `-e` | CSS selector to exclude (can be repeated) |
| `--html` | | Show raw_html (first 5000 chars) |

**Examples:**

```bash
uv run fetch https://example.com/blog
uv run fetch https://example.com/blog --title "Entry Title"
uv run fetch https://example.com/blog --screenshot
uv run fetch https://example.com/blog --exclude ".sidebar" --exclude ".ad-slot"
uv run fetch https://example.com/blog --html
```

### generate-singlehop-eval-dataset

Generate single-hop evaluation dataset for Research Agent using RAGAS.

Creates QA pairs from individual entries, testing the agent's ability
to retrieve and answer questions from single documents.

```bash
generate-singlehop-eval-dataset [options] <subcommand>
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset-name` | `singlehop-evaluation` | Dataset name for directory |

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `sample` | Step 1: Sample diverse entries from database (K-means clustering) |
| `generate` | Step 2: Generate QA pairs with RAGAS TestsetGenerator |
| `upload` | Step 3: Upload generated QA pairs to Langfuse Dataset |
| `all` | Run all steps: sample → generate → upload |

#### sample

```bash
generate-singlehop-eval-dataset sample [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--n-samples` | 15 | Number of entries to sample per language |
| `--min-content-length` | 1000 | Minimum content length for entries |

#### generate

```bash
generate-singlehop-eval-dataset generate [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset-size` | 10 | Number of QA samples per pattern |
| `--llm-model` | `$EVAL_DATA_LLM_MODEL` | LLM model for generation |
| `--embedding-model` | `$EVAL_DATA_EMBEDDING_LLM_MODEL` | Embedding model |

#### upload

```bash
generate-singlehop-eval-dataset upload [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--langfuse-dataset-name` | Same as `--dataset-name` | Langfuse dataset name |

**Required Environment Variables:**

- `DATABASE_URL`
- `OPENAI_API_KEY`
- `LANGFUSE_PUBLIC_KEY` (for upload)
- `LANGFUSE_SECRET_KEY` (for upload)

**Examples:**

```bash
uv run generate-singlehop-eval-dataset sample --n-samples 20
uv run generate-singlehop-eval-dataset generate --dataset-size 15
uv run generate-singlehop-eval-dataset upload
uv run generate-singlehop-eval-dataset all
```

**Output:**

```text
evaluation/<dataset-name>/
├── data/
│   ├── eval_targets.json    # Sampled entries
│   └── qa/
│       └── eval_qa.json     # Generated QA pairs
└── results/                 # Evaluation results
```

### generate-filtering-dataset

Generate filtering evaluation dataset from labeled entries.

```bash
generate-filtering-dataset [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--label` | `eval-filtering` | Label name to filter entries |
| `--limit` | None | Maximum number of entries to fetch |
| `--dataset-name` | `filtering-evaluation` | Dataset name |
| `--no-upload` | | Skip uploading to Langfuse Dataset |

**Examples:**

```bash
uv run generate-filtering-dataset
uv run generate-filtering-dataset --label my-label
uv run generate-filtering-dataset --limit 100
```

### run-filtering-on-dataset

Run filtering on Langfuse dataset items.

```bash
run-filtering-on-dataset [options]
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset-name` | `filtering-evaluation` | Langfuse dataset name |
| `--limit` | None | Maximum number of items to process |
| `--dry-run` | | Show what would be done without making changes |

**Examples:**

```bash
uv run run-filtering-on-dataset
uv run run-filtering-on-dataset --limit 10
uv run run-filtering-on-dataset --dry-run
```

### generate-multihop-eval-dataset

Generate multi-hop evaluation dataset for Research Agent.

Creates QA pairs that require information from multiple entries,
testing the agent's ability to retrieve and synthesize across documents.

```bash
generate-multihop-eval-dataset [options] <subcommand>
```

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--dataset-name` | `multihop-evaluation` | Dataset name for directory |

**Subcommands:**

| Subcommand | Description |
|------------|-------------|
| `cluster` | Step 1: Cluster entries by embedding similarity (K-means) |
| `generate` | Step 2: Generate multi-hop questions from clusters |
| `filter` | Step 3: Filter out shortcut-solvable questions |
| `all` | Run all steps: cluster → generate → filter |
| `upload` | Step 4: Upload filtered questions to Langfuse Dataset |

#### cluster

```bash
generate-multihop-eval-dataset cluster [options]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--n-clusters` | 20 | Number of clusters to create |
| `--min-cluster-size` | 2 | Minimum entries per cluster |
| `--min-content-length` | 500 | Minimum content length for entries |

#### generate

```bash
generate-multihop-eval-dataset generate [options]
```

Selects the 2 most similar entries from each cluster and generates questions.

| Option | Default | Description |
|--------|---------|-------------|
| `--questions-per-cluster` | 2 | Number of questions per cluster |
| `--max-clusters` | None | Maximum clusters to process |
| `--min-similarity` | 0.5 | Minimum cosine similarity between entries |
| `--llm-model` | `$EVAL_DATA_LLM_MODEL` | LLM model for generation |

#### filter

```bash
generate-multihop-eval-dataset filter [options]
```

Filters out questions that can be answered from a single entry (shortcuts).

| Option | Default | Description |
|--------|---------|-------------|
| `--llm-model` | `$EVAL_DATA_LLM_MODEL` | LLM model for shortcut detection |

#### upload

```bash
generate-multihop-eval-dataset upload [options]
```

Uploads filtered questions to Langfuse Dataset for evaluation with `batch-eval`.

| Option | Default | Description |
|--------|---------|-------------|
| `--langfuse-dataset-name` | Same as `--dataset-name` | Langfuse dataset name |

**Required Environment Variables:**

- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` (optional)

**Examples:**

```bash
uv run generate-multihop-eval-dataset cluster --n-clusters 20
uv run generate-multihop-eval-dataset generate --questions-per-cluster 2
uv run generate-multihop-eval-dataset filter
uv run generate-multihop-eval-dataset upload
uv run generate-multihop-eval-dataset all
```

**Output:**

```text
evaluation/<dataset-name>/
├── data/
│   ├── clusters.json        # Entry clusters
│   └── multihop_qa.json     # Generated QA pairs
└── results/                 # Evaluation results
```

---

## Environment Variables

### Using 1Password CLI

```bash
cd agent
op run --env-file=../.env.op -- uv run agent-cli research "test query"

cd worker
op run --env-file=.env.op -- uv run worker
```

### Using .env file

```bash
cp .env.example .env
# Edit .env
uv run <command>
```

### Required Variables (Agent)

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for OpenAI-compatible LLM service |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible LLM service |
| `API_BASE_URL` | Next.js API URL |
| `INTERNAL_API_TOKEN` | Internal API authentication token |

### Required Variables (Worker)

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `TEMPORAL_HOST` | Temporal server address |
| `OPENAI_API_KEY` | API key for OpenAI-compatible LLM service |
| `OPENAI_BASE_URL` | Base URL for OpenAI-compatible LLM service |

See `worker/README.md` for complete environment variable documentation.
