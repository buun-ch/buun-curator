# Worker (Temporal Workflows)

Workflow and Activity implementation follows the [Temporal Python SDK guide](https://docs.temporal.io/develop/python/core-application). Key conventions:

- Workflow `run` methods take a single Pydantic model argument for proper serialization
- Activity functions also use Pydantic Input/Output pattern
- Workflow I/O models are defined in `models/workflow_io.py` (Pydantic with `CamelCaseModel`)
- Activity I/O models are defined in `models/activity_io.py` (Pydantic with `BaseModel`)

For worker-specific terminology (Crawl, Fetch, Distill), see [Terminology](./terminology.md).

## Workflow Hierarchy Diagram

```text
AllFeedsIngestionWorkflow (Parent - batch feed processing)
├── list_feeds Activity
├── get_app_settings Activity
└── SingleFeedIngestionWorkflow (child) × N feeds
    ├── crawl_single_feed Activity
    ├── ScheduleFetchWorkflow (child) ─ when enable_content_fetch=true
    │   ├── DomainFetchWorkflow (child) × N domains
    │   │   └── fetch_single_content Activity (sequential with delay)
    │   └── ContentDistillationWorkflow (fire-and-forget, batches of 5) ─ when auto_distill=true
    ├── fetch_single_content Activity ─ when enable_content_fetch=false (HTML processing)
    ├── ContentDistillationWorkflow (fire-and-forget) ─ when auto_distill=true
    └── notify_update Local Activity (SSE progress)

ReprocessEntriesWorkflow (Standalone - reprocess existing entries)
├── get_entries Activity
├── fetch_contents Activity
├── ContentDistillationWorkflow (child, waits for completion)
└── notify_update Local Activity (SSE progress)

ContentDistillationWorkflow (Standalone - batch content distillation)
├── get_app_settings Activity
├── get_entries_for_distillation Activity
├── distill_entry_content Activity
├── save_distilled_entries Activity
├── SummarizationEvaluationWorkflow (fire-and-forget) ─ when AI_EVALUATION_ENABLED=true
└── notify_update Local Activity (SSE progress)

GlobalGraphUpdateWorkflow (Standalone/Scheduled - batch graph update)
├── get_entries_for_graph_update Activity (entries with graphAdded=false)
├── get_entry Activity × N entries (fetch filteredContent)
├── add_to_global_graph_bulk Activity
└── mark_entries_graph_added Activity

ContextCollectionWorkflow (Standalone - context extraction & enrichment)
├── ExtractEntryContextWorkflow (child) × N entries
│   ├── get_entry Activity
│   ├── extract_entry_context Activity (LLM)
│   └── save_entry_context Activity
├── search_github_candidates Activity
├── rerank_github_results Activity (LLM)
├── fetch_github_readme Activity
├── save_github_enrichment Activity
├── save_entry_links Activity
└── notify_update Local Activity (SSE progress)

FetchEntryLinksWorkflow (Standalone - fetch URLs as entry enrichments)
├── fetch_and_save_entry_links Activity
└── notify_update Local Activity (SSE progress)

DeleteEnrichmentWorkflow (Standalone - delete enrichment from database)
├── delete_enrichment Activity
└── notify_update Local Activity (SSE progress)

DeepResearchWorkflow (Standalone - deep research, currently unused)
└── (implementation pending)

TranslationWorkflow (Standalone - translation with DeepL or Microsoft)
├── get_app_settings Activity
├── get_entries_for_translation Activity
├── deepl_translate_articles / ms_translate_articles Activity (based on provider)
├── save_translations Activity
└── notify_update Local Activity (SSE progress)

PreviewFetchWorkflow (Standalone - single URL preview)
└── fetch_single_content Activity

SearchReindexWorkflow (Standalone - rebuild Meilisearch index)
├── clear_search_index Activity (optional, when clean=true)
├── init_search_index Activity
├── get_entry_ids_for_indexing Activity (cursor-based pagination)
└── index_entries_batch Activity

SearchPruneWorkflow (Standalone - remove orphaned documents from index)
├── get_orphaned_document_ids Activity (compare index vs DB)
└── remove_documents_from_index Activity

EntriesCleanupWorkflow (Standalone/Scheduled - delete old entries)
└── cleanup_old_entries Activity (delete via REST API)

GraphRebuildWorkflow (Standalone - rebuild LightRAG/Memgraph knowledge graph)
├── reset_global_graph Activity (optional, when clean=true)
├── get_entry_ids_for_indexing Activity (cursor-based pagination)
└── fetch_and_add_to_graph_bulk Activity (fetch entries + batch add to graph)

EvaluationWorkflow (Fire-and-forget - RAGAS evaluation for agent Q&A)
└── evaluate_ragas Activity (compute metrics + record to Langfuse)

SummarizationEvaluationWorkflow (Fire-and-forget - RAGAS evaluation for summarization)
└── evaluate_summarization Activity (compute metrics + record to Langfuse)

EmbeddingBackfillWorkflow (Standalone - compute embeddings for recommendations)
├── get_entries_for_embedding Activity (cursor-based pagination)
└── compute_embeddings Activity (FastEmbed + save via API)
```

## Embeddings and Recommendations

Entry embeddings enable "Recommended" sort mode, which ranks entries by similarity
to user preferences using pgvector's cosine distance.

### Architecture

```text
┌─────────────────┐    filteredContent     ┌──────────────────┐
│  ContentDist-   │ ─────────────────────► │  entries table   │
│  illationWF     │    (save distilled)    │  (no embedding)  │
└─────────────────┘                        └────────┬─────────┘
                                                    │
                                                    │ Backfill workflow
                                                    ▼
┌─────────────────┐    compute + save      ┌──────────────────┐
│  EmbeddingBack- │ ─────────────────────► │  entries table   │
│  fillWorkflow   │    (batch process)     │  (with embedding)│
└─────────────────┘                        └────────┬─────────┘
                                                    │
                                                    │ Query time
                                                    ▼
┌─────────────────┐    cosine distance     ┌──────────────────┐
│  GET /api/      │ ◄───────────────────── │  pgvector        │
│  entries?sort=  │    (embedding <=>)     │  (similarity)    │
│  recommended    │                        │                  │
└─────────────────┘                        └──────────────────┘
```

### Embedding Model

- **Model**: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- **Dimensions**: 768
- **Library**: FastEmbed (ONNX runtime for CPU inference)

### Content Priority for Embeddings

When computing embeddings: `filteredContent` → `summary` → `title`

### Preference Vector

The "Recommended" sort uses the average embedding of entries with `preference='up'`
as the target vector. Entries are ranked by cosine distance (lower = more similar).

```sql
-- Compute preference vector (average of upvoted entries)
SELECT AVG(embedding)::text FROM entries WHERE preference = 'up' AND embedding IS NOT NULL

-- Query entries by similarity
SELECT *, (embedding <=> preference_vector) as similarity_score
FROM entries
WHERE embedding IS NOT NULL
ORDER BY similarity_score ASC
```

### CLI Usage

```bash
# Compute embeddings for all entries without them
uv run trigger embedding-backfill

# With custom batch size
uv run trigger embedding-backfill --batch-size 200
```

## Global Knowledge Graph Integration

**Status:** Graph building is implemented but usage is still being determined.

The global knowledge graph (`buun_curator`) stores extracted entities and relationships
from all ingested entries. The backend is configurable (default: LightRAG with Memgraph storage).

### Decoupled Architecture

Graph updates are **decoupled** from content distillation for better performance and reliability:

1. **`ContentDistillationWorkflow`**: Focuses on content filtering and summarization only.
   After saving distilled entries, the `graphAddedAt` column remains `NULL`.

2. **`GlobalGraphUpdateWorkflow`**: Dedicated workflow for graph updates, runs on a schedule.
   Fetches entries with `graphAddedAt=NULL` and `filteredContent` present, adds them to the
   graph in bulk, then marks them with `graphAddedAt=NOW()`.

This separation allows:

- Fast content distillation without blocking on graph operations
- Independent scaling of graph update workload
- Retry failed graph updates without re-running distillation
- Configurable batch sizes and schedules

### Graph Update Schedule

```bash
# Set graph update schedule (every hour)
uv run schedule graph set --interval 1h

# Set with cron expression
uv run schedule graph set --cron "0 * * * *"

# Set with custom batch size
uv run schedule graph set --interval 1h --batch-size 100

# Show/pause/resume/delete/trigger
uv run schedule graph show
uv run schedule graph pause
uv run schedule graph resume
uv run schedule graph delete
uv run schedule graph trigger
```

### Content Priority

When adding to the graph: `filteredContent` (entries without `filteredContent` are skipped)

## SSE Notification System

Real-time workflow progress is pushed to the browser via Server-Sent Events (SSE).
The system uses Temporal Query to fetch progress state, keeping the notification payload minimal.

### Architecture

```text
┌─────────────────┐     notify_update      ┌──────────────────┐
│                 │    (workflowId only)   │                  │
│  Temporal       │ ─────────────────────► │  Next.js API     │
│  Worker         │                        │  /api/events/send│
│                 │                        │                  │
└─────────────────┘                        └────────┬─────────┘
       ▲                                            │
       │                                            │ Query Temporal
       │ Temporal Query                             │ for progress
       │ (get_progress)                             ▼
       │                                   ┌──────────────────┐
       └───────────────────────────────────┤  Temporal Server │
                                           └──────────────────┘
                                                    │
                                                    │ SSE broadcast
                                                    │ (full progress)
                                                    ▼
                                           ┌──────────────────┐
                                           │  Browser         │
                                           │  (SSE Client)    │
                                           └──────────────────┘
```

**Flow:**

1. Workflow calls `notify_update` local activity with only `workflowId`
2. Next.js API receives the notification via `/api/events/send`
3. API queries Temporal for full `WorkflowProgress` using Query handler
4. API broadcasts full progress to all connected browsers via SSE

### Throttle and Debounce Strategy

To prevent notification floods during rapid progress updates:

| Layer  | Strategy | Interval | Purpose                                 |
| ------ | -------- | -------- | --------------------------------------- |
| Worker | Throttle | 300ms    | Skip notifications if last was recent   |
| API    | Debounce | 100ms    | Coalesce rapid updates before broadcast |

**Worker-side throttle** (`_NOTIFY_THROTTLE_SECONDS = 0.3`):

```python
async def _notify_update(self, force: bool = False) -> None:
    now = workflow.now().timestamp()
    if not force and (now - self._last_notify_time) < self._NOTIFY_THROTTLE_SECONDS:
        return  # Skip this notification
    self._last_notify_time = now
    # ... send notification
```

**API-side debounce** delays broadcast until updates settle:

```typescript
function scheduleUpdate(workflowId: string): void {
  const existingTimer = pendingUpdates.get(workflowId);
  if (existingTimer) clearTimeout(existingTimer);

  const timer = setTimeout(() => {
    pendingUpdates.delete(workflowId);
    fetchAndBroadcastProgress(workflowId);
  }, UPDATE_DEBOUNCE_MS);
  pendingUpdates.set(workflowId, timer);
}
```

### Workflow Progress State

Each workflow maintains progress state via a Pydantic model and exposes it through a Query handler:

```python
class ReprocessEntriesProgress(WorkflowProgress):
    """Progress for ReprocessEntriesWorkflow."""
    workflow_type: str = "ReprocessEntries"
    total_entries: int = 0
    entries_fetched: int = 0
    entries_distilled: int = 0
    entry_progress: dict[str, EntryProgressState] = Field(default_factory=dict)

@workflow.defn
class ReprocessEntriesWorkflow:
    def __init__(self) -> None:
        self._progress = ReprocessEntriesProgress()
        self._last_notify_time: float = 0

    @workflow.query
    def get_progress(self) -> ReprocessEntriesProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress
```

**Important:** Use `workflow.now()` for timestamps in workflows to maintain determinism:

```python
# utils/date.py
from temporalio import workflow

def workflow_now_iso() -> str:
    """Get current UTC timestamp in ISO 8601 format (deterministic)."""
    return workflow.now().isoformat()
```

### Hierarchical Progress System

Workflows form a parent-child hierarchy, and progress is tracked at each level.
The frontend aggregates child progress to display accurate real-time status.

#### Progress Hierarchy

```text
AllFeedsIngestionProgress (top-level)
├── feedsTotal, feedsCompleted, currentBatch, totalBatches
├── entriesCreated, contentsFetched, entriesDistilled
└── children:
    └── SingleFeedIngestionProgress × N feeds
        ├── feedId, feedName, parentWorkflowId
        ├── totalEntries, entriesCreated, contentsFetched, entriesDistilled
        └── children:
            └── ScheduleFetchProgress
                ├── totalEntries, totalDomains, domainsCompleted
                └── children:
                    └── DomainFetchProgress × N domains
                        ├── domain, currentEntryIndex, currentEntryTitle
                        ├── entriesFetched, entriesDistilled, entriesFailed
                        └── entry_progress: {entryId -> EntryProgressState}
                            └── status: pending|fetching|fetched|distilling|completed|error
```

#### Parent-Child Linking

Child workflows include `parent_workflow_id` in their input and progress:

```python
# Parent workflow starting child
handle = await workflow.start_child_workflow(
    SingleFeedIngestionWorkflow.run,
    SingleFeedIngestionInput(
        feed_id=feed_id,
        parent_workflow_id=wf_info.workflow_id,  # Link to parent
        ...
    ),
    id=child_wf_id,
)

# Child progress includes parent reference
class SingleFeedIngestionProgress(WorkflowProgress):
    parent_workflow_id: str = ""  # Serialized as parentWorkflowId
```

#### Frontend Hierarchical Store

The Zustand store (`stores/workflow-store.ts`) maintains the hierarchy:

```typescript
interface WorkflowStoreState {
  // Top-level workflows only (no parentWorkflowId)
  workflows: Record<string, WorkflowProgressNode>;
  // Child workflows waiting for their parent to arrive
  orphanWorkflows: Record<string, WorkflowProgressNode>;
}

interface WorkflowProgressNode extends WorkflowProgress {
  children: Record<string, WorkflowProgressNode>;  // Nested children
}
```

When SSE delivers a child workflow update:

1. If parent exists in store → add to `parent.children`
2. If parent not yet arrived → store in `orphanWorkflows`
3. When parent arrives → collect orphans and attach as children

#### Aggregating entry_progress for Toast

The actual per-entry progress (`entry_progress`) lives in `DomainFetchProgress`.
To show accurate progress in a `SingleFeedIngestionWorkflow` toast, the frontend
traverses the hierarchy to collect all entry states:

```typescript
// lib/workflow-toast.ts
function collectEntryProgress(
  workflow: WorkflowProgressNode
): Record<string, EntryProgressState> {
  const result: Record<string, EntryProgressState> = {};

  // If DomainFetch, collect its entry_progress
  if (isDomainFetchProgress(workflow) && workflow.entryProgress) {
    Object.assign(result, workflow.entryProgress);
  }

  // Recursively collect from children
  for (const child of Object.values(workflow.children)) {
    Object.assign(result, collectEntryProgress(child));
  }

  return result;
}

// Count by status to show "fetch 3/5, distill 2/5"
const counts = countEntryStatuses(collectEntryProgress(workflow));
const fetched = counts.fetched + counts.distilling + counts.completed;
const distilled = counts.completed;
```

#### Toast Updates on Child Progress

When any child workflow sends an SSE update, the frontend finds the top-level
parent and updates its toast with the latest aggregated progress:

```typescript
// components/providers/sse-provider.tsx
const showWorkflowToast = useCallback((progress: WorkflowProgress) => {
  const { workflowId, parentWorkflowId } = progress;

  // Find top-level parent
  const topLevelId = parentWorkflowId
    ? findTopLevelParentId(state, parentWorkflowId)
    : workflowId;

  if (topLevelId) {
    updateWorkflowToast(topLevelId);  // Re-render with aggregated children
  }
}, []);
```

### Progress Classes Summary

| Workflow              | Progress Class                | Key Fields                                                             |
| --------------------- | ----------------------------- | ---------------------------------------------------------------------- |
| `AllFeedsIngestion`   | `AllFeedsIngestionProgress`   | `feedsTotal`, `feedsCompleted`, `currentBatch`, `totalBatches`         |
| `SingleFeedIngestion` | `SingleFeedIngestionProgress` | `feedId`, `feedName`, `entriesCreated`, `contentsFetched`              |
| `ScheduleFetch`       | `ScheduleFetchProgress`       | `totalDomains`, `domainsCompleted`, `skippedCount`                     |
| `DomainFetch`         | `DomainFetchProgress`         | `domain`, `entry_progress`, `entriesFetched`, `entriesDistilled`       |
| `ReprocessEntries`    | `ReprocessEntriesProgress`    | `entry_progress`, `entriesFetched`, `entriesDistilled`                 |
| `Translation`         | `TranslationProgress`         | `provider`, `entry_progress`, `totalEntries`, `entriesTranslated`      |
| `ContentDistillation` | `ContentDistillationProgress` | `entry_progress`, `totalEntries`, `entriesDistilled`                   |
| `ContextCollection`   | `ContextCollectionProgress`   | `entry_progress`, `successfulExtractions`, `enrichmentCandidatesCount` |

All progress classes inherit from `WorkflowProgress` base class which includes:
`workflow_id`, `workflow_type`, `status`, `current_step`, `message`, `started_at`, `updated_at`, `error`.

### Reconnection Handling

When a browser reconnects, it fetches active workflows to restore state:

```typescript
// On SSE connect/reconnect
const fetchActiveWorkflows = async () => {
  const response = await fetch("/api/workflows/active");
  const workflows = await response.json();
  for (const wf of workflows) {
    if (wf.progress) handleWorkflowUpdate(wf.progress);
  }
};
```

### SSE Key Files

| Location | File                                | Purpose                                         |
| -------- | ----------------------------------- | ----------------------------------------------- |
| Worker   | `activities/notify.py`              | `notify_update` local activity                  |
| Worker   | `models/workflow_io.py`             | `WorkflowProgress` Pydantic models (camelCase)  |
| Worker   | `workflows/*.py`                    | `_notify_update()` method, `get_progress` query |
| Next.js  | `app/api/events/send/route.ts`      | Receive notification, query Temporal, broadcast |
| Next.js  | `app/api/events/route.ts`           | SSE endpoint for browsers                       |
| Next.js  | `app/api/workflows/active/route.ts` | List running workflows for reconnection         |
| Next.js  | `lib/temporal.ts`                   | `queryWorkflowProgress()` function              |
| Frontend | `hooks/use-sse.ts`                  | SSE hook with event handlers                    |
| Frontend | `components/sse/sse-provider.tsx`   | SSE context and cache integration               |
| Frontend | `stores/workflow-store.ts`          | Zustand store for workflow state                |

## Workflows

### AllFeedsIngestionWorkflow

Parent workflow that orchestrates feed ingestion using child workflows:

**Steps:**

1. Get app settings (target language) if auto_distill enabled
2. List all feeds via `list_feeds` Activity
3. Process feeds in batches with concurrency limit (`max_concurrent`)
4. Start `SingleFeedIngestionWorkflow` for each feed as child workflow
5. Aggregate results from all child workflows

**Benefits:**

- **Parallel processing**: Configurable concurrency via `FEED_INGESTION_CONCURRENCY`
- **Fault isolation**: One feed failure doesn't affect others
- **Better observability**: Each feed visible as separate workflow in Temporal UI
- **Scalable**: Multiple workers can process feeds concurrently

### SingleFeedIngestionWorkflow

Processes a single feed (used as child workflow or standalone):

**Steps:**

1. **Crawl**: Fetch feed entries via `crawl_single_feed`, create new entries in DB
2. **Fetch**: Get full entry content:
   - URL fetch mode (`enable_content_fetch=true`): Use `ScheduleFetchWorkflow` → `DomainFetchWorkflow`
     for domain-based rate limiting
   - HTML processing mode (`enable_content_fetch=false`): Process `feed_content` HTML via
     `fetch_single_content`, then start `ContentDistillationWorkflow` in fire-and-forget mode
3. **Notify**: Send SSE progress updates via local activities

**Fire-and-Forget Distillation:** When `auto_distill=true`, distillation runs asynchronously via
`ContentDistillationWorkflow` with `ParentClosePolicy.ABANDON`. The workflow returns immediately
after content fetch, allowing users to read entries while summarization happens in the background.

**Content Fetching**: See [Content Fetching](./fetch-content.md) for extraction rules.

### ScheduleFetchWorkflow

Orchestrates content fetching with domain-based rate limiting and batched distillation:

**Steps:**

1. Filter out YouTube URLs (skip fetching)
2. Group entries by domain
3. Start `DomainFetchWorkflow` for each domain in parallel
4. Poll domain workflows using `asyncio.wait(FIRST_COMPLETED)`
5. As entries complete, batch them (5 at a time) and start `ContentDistillationWorkflow`
   in fire-and-forget mode
6. Handle remaining entries (<5) at the end

**Benefits:**

- Different domains fetched in parallel for efficiency
- Same domain requests spaced out to avoid rate limits
- Distillation starts early as entries become available (not after all domains complete)
- Batched distillation reduces LLM call overhead
- Works correctly across multiple Temporal workers

### DomainFetchWorkflow

Handles sequential fetching for a single domain:

**Steps:**

1. For each entry in the domain:
   - Apply delay before subsequent requests (not before first)
   - Execute `fetch_single_content` Activity
   - Record success/failure
2. Return fetched entry IDs to parent workflow

**Rate Limiting:** Configurable delay between requests (`delay_seconds`, default: 2.0s).

**Note:** Distillation is handled by `ScheduleFetchWorkflow` which batches entries
from multiple domains for efficient processing.

### ReprocessEntriesWorkflow

Reprocess existing entries by ID (used by UI refetch button):

**Steps:**

1. Get entry details from REST API via `get_entries`
2. Fetch content via `fetch_contents` Activity (optional)
3. Execute `ContentDistillationWorkflow` as child workflow and wait for completion (optional)
4. Send SSE progress updates

**Child Workflow:** Unlike `ScheduleFetchWorkflow` and `SingleFeedIngestionWorkflow` which use
fire-and-forget distillation, this workflow waits for `ContentDistillationWorkflow` to complete.
This is appropriate because the user explicitly requested reprocessing and expects to see the
final result.

### ContentDistillationWorkflow

Standalone content distillation (filtering + summarization):

**Steps:**

1. Get app settings (target language)
2. Get entries to distill (specific IDs or all undistilled with content) via `get_entries_for_distillation`
3. Filter and summarize content in batches using `distill_entry_content`
4. Save distilled entries via `save_distilled_entries`
5. If `AI_EVALUATION_ENABLED=true`: Start `SummarizationEvaluationWorkflow` in fire-and-forget mode

**Note:** Graph updates are handled separately by `GlobalGraphUpdateWorkflow` running on a schedule.
This decoupled architecture allows faster distillation and independent scaling.

**Summarization Evaluation:** When enabled, the workflow starts `SummarizationEvaluationWorkflow`
as a fire-and-forget child workflow. Each entry gets a deterministic trace_id generated from
`entry_id` and `batch_trace_id`, allowing Langfuse to correlate evaluation scores with the
original distillation traces.

### PreviewFetchWorkflow

Fetches content from a single URL for preview purposes (used when testing extraction rules):

**Steps:**

1. Execute `fetch_single_content` Activity with provided URL and extraction rules
2. Return fetched content or error

### SearchReindexWorkflow

Rebuilds the Meilisearch full-text search index from all entries in the database.
Supports CJK languages (Chinese, Japanese, Korean) and 8 languages total.

**Input:**

- `batch_size`: Number of entries to process per batch (default: 500)
- `clean`: Delete all documents before reindexing (default: false)

**Steps:**

1. If `clean=true`, delete all documents via `clear_search_index` Activity
2. Initialize Meilisearch index with searchable attributes and filters
3. Fetch entry IDs using cursor-based pagination (API max limit: 100)
4. For each batch:
   - Fetch full entry data via API
   - Index entries in Meilisearch via `index_entries_batch` Activity
5. Return total indexed count and any errors

**CLI Usage:**

```bash
# Rebuild index (add/update only)
uv run trigger reindex

# Rebuild index after clearing all documents
uv run trigger reindex --clean
```

**Indexed Fields:**

| Field             | Purpose                                        |
| ----------------- | ---------------------------------------------- |
| `title`           | Entry title (searchable, highlighted)          |
| `summary`         | AI-generated summary (searchable, highlighted) |
| `filteredContent` | Extracted entry content                        |
| `feedContent`     | Original RSS/Atom content                      |
| `author`          | Author name                                    |
| `feedId`          | Filter by feed                                 |
| `publishedAt`     | Sort by date                                   |

**Note:** `isRead` and `isStarred` are NOT indexed in Meilisearch. These fields change
frequently and are fetched from the database when displaying search results.

### SearchPruneWorkflow

Removes orphaned documents from the Meilisearch index. Orphaned documents are
entries that exist in the search index but have been deleted from the database.

**Input:**

- `batch_size`: Batch size for fetching document IDs from Meilisearch (default: 1000)

**Steps:**

1. Fetch all document IDs from Meilisearch via `get_orphaned_document_ids` Activity
2. Fetch all entry IDs from the database
3. Find orphaned IDs (in index but not in DB)
4. Remove orphaned documents via `remove_documents_from_index` Activity

**CLI Usage:**

```bash
# Remove orphaned documents
uv run trigger prune
```

**When to use:**

- After deleting entries from the database
- When search returns 404 errors for entries
- Periodic maintenance to clean up stale index entries

### EntriesCleanupWorkflow

Deletes old entries that meet cleanup criteria. Designed to run on a Temporal schedule
for automatic database maintenance.

**Cleanup Criteria:**

- `isRead = true` (already read)
- `isStarred = false` (not starred)
- `preference != 'up'` (not upvoted, i.e., `null` or `'down'`)
- `publishedAt` is older than the specified number of days

**Input:**

- `older_than_days`: Delete entries older than this many days (default: 7)
- `dry_run`: If true, count entries without deleting (default: false)

**Steps:**

1. Execute `cleanup_old_entries` Activity:
   - Calls REST API `/api/entries/cleanup`
   - Deletes entries matching criteria or counts if dry_run
2. Return deleted count and cutoff date

**CLI Usage (manual trigger):**

```bash
# Delete entries older than 7 days (default)
uv run trigger cleanup

# Delete entries older than 14 days
uv run trigger cleanup --days 14

# Dry run (count without deleting)
uv run trigger cleanup --dry-run
```

**Schedule CLI:**

```bash
# Set cleanup schedule (every day)
uv run schedule cleanup set --interval 1d

# Set with custom age threshold
uv run schedule cleanup set --interval 1d --days 14

# Set with cron expression (every day at 3am JST)
uv run schedule cleanup set --cron "0 3 * * *" --timezone "Asia/Tokyo"

# Manage schedule
uv run schedule cleanup show
uv run schedule cleanup pause
uv run schedule cleanup resume
uv run schedule cleanup delete
uv run schedule cleanup trigger
```

**Related Tables:**

Entries deleted by this workflow will cascade delete related records:

- `entry_enrichments` (via `onDelete: "cascade"`)
- `entry_links` (via `onDelete: "cascade"`)

### GlobalGraphUpdateWorkflow

Processes entries pending graph update and adds them to the global knowledge graph.
Designed to run on a Temporal schedule for incremental graph updates.

**Input:**

- `entry_ids`: List of entry IDs to process (optional, auto-selects if empty)
- `batch_size`: Maximum entries per run (default: 50)

**Steps:**

1. Fetch pending entries via `get_entries_for_graph_update` Activity
   - Queries entries with `graphAddedAt=NULL` and `filteredContent` present
2. For each entry:
   - Fetch full entry data via `get_entry` Activity
   - Build graph episode from `filteredContent`
3. Add episodes to graph in bulk via `add_to_global_graph_bulk` Activity
4. Mark entries as processed via `mark_entries_graph_added` Activity
   - Sets `graphAddedAt=NOW()` to prevent reprocessing

**Database Column:**

The `entries.graphAddedAt` column tracks when each entry was added to the graph:

- `NULL`: Entry has not been added to the graph (pending)
- Timestamp: Entry was added at this time

**API Filter:**

```text
GET /api/entries?graphAdded=false
```

Returns entries with `graphAddedAt=NULL` AND `filteredContent` present.

**Schedule CLI:**

```bash
# Set graph update schedule
uv run schedule graph set --interval 1h
uv run schedule graph set --cron "0 * * * *" --timezone "Asia/Tokyo"

# Manage schedule
uv run schedule graph show
uv run schedule graph pause
uv run schedule graph resume
uv run schedule graph delete
uv run schedule graph trigger
```

**CLI (manual trigger):**

```bash
# Add pending entries to graph
uv run trigger graph-update

# With custom batch size
uv run trigger graph-update --batch-size 100
```

**Difference from GraphRebuildWorkflow:**

| Aspect          | GlobalGraphUpdateWorkflow     | GraphRebuildWorkflow           |
| --------------- | ----------------------------- | ------------------------------ |
| Purpose         | Incremental updates           | Full rebuild                   |
| CLI             | `uv run trigger graph-update` | `uv run trigger graph-rebuild` |
| Scheduling      | Runs on schedule              | Manual trigger                 |
| Entry selection | Only `graphAddedAt=NULL`      | All entries                    |
| Clean option    | No                            | Yes (`--clean`)                |

### GraphRebuildWorkflow

Rebuilds the LightRAG/Memgraph knowledge graph from all entries in the database.
Uses LightRAG with Memgraph storage to extract entities and relationships from entry content.

**Input:**

- `batch_size`: Number of entries to process per batch (default: 20)
- `clean`: Delete all nodes before rebuilding (default: false)

**Steps:**

1. If `clean=true`, delete all nodes and relationships via `reset_global_graph` Activity
2. Fetch entry IDs using cursor-based pagination via `get_entry_ids_for_indexing` Activity
3. For each batch:
   - Fetch entries and add to graph via `fetch_and_add_to_graph_bulk` Activity
     (combines fetching and graph insertion to avoid Temporal payload size limits)
   - Content priority: `filteredContent` → `full_content` → `feed_content`
4. Return total added count and any errors

**CLI Usage:**

```bash
# Rebuild graph (add new entries only)
uv run trigger graph-rebuild

# Rebuild graph after clearing all nodes
uv run trigger graph-rebuild --clean

# With custom batch size
uv run trigger graph-rebuild --clean --batch-size 10
```

**Environment Variables (Helm configurable):**

| Variable               | Description                    | Default                                                       |
| ---------------------- | ------------------------------ | ------------------------------------------------------------- |
| `EMBEDDING_MODEL`      | FastEmbed model for embeddings | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` |
| `EMBEDDING_DIMENSIONS` | Embedding vector dimensions    | `768`                                                         |
| `EMBEDDING_THREADS`    | ONNX Runtime thread limit      | unlimited                                                     |

**Known Issues:**

- LLM extraction errors during entity extraction can cause batch failures
- Large entries may cause long processing times for a single `ainsert` call

### TranslationWorkflow

Unified workflow for translating entries using DeepL or Microsoft Translator API:

**Input:**

- `entry_ids`: List of entry IDs to translate (optional, auto-selects if not provided)
- `provider`: Translation provider (`"deepl"` or `"microsoft"`, default: `"microsoft"`)

**Steps:**

1. Get app settings (target language)
2. Get entries to translate via `get_entries_for_translation`
3. Initialize entry progress tracking for SSE notifications
4. Translate using `deepl_translate_articles` or `ms_translate_articles` based on provider
5. Save translations via `save_translations`
6. Send SSE progress updates via `notify_update`

**Environment Variable:**

- `TRANSLATION_PROVIDER`: Default provider (`"deepl"` or `"microsoft"`)

### ContextCollectionWorkflow

High-level workflow for collecting and analyzing entry contexts.
See [Context Extraction](./context.md) for details.

**Steps:**

1. Extract contexts via `ExtractEntryContextWorkflow` for each entry
2. Analyze contexts and create execution plan
3. Collect enrichment candidates (Software entities needing GitHub info)
4. Execute GitHub search and LLM re-ranking for each candidate
5. Fetch GitHub README via `fetch_github_readme`
6. Save GitHub enrichments to database via `save_github_enrichment`
7. Save extracted links via `save_entry_links`

### ExtractEntryContextWorkflow

Sub-workflow for extracting structured context from an entry.
See [Context Extraction](./context.md) for details.

**Steps:**

1. Fetch entry data via `get_entry` Activity
2. Extract content (tries `filteredContent` → `fullContent` → `feedContent`)
3. Execute LLM context extraction via `extract_entry_context` Activity
4. Save context to database via `save_entry_context`

**Extracted Data:** Domain classification, entities, relationships, key points, extracted links.

### FetchEntryLinksWorkflow

Fetches content from URLs extracted during context collection and saves as entry enrichments.
See [Context Extraction](./context.md) for details.

**Steps:**

1. Execute `fetch_and_save_entry_links` Activity with entry ID and URLs
2. Each URL is fetched, converted to markdown, and saved as an enrichment
3. Send SSE progress updates

### DeleteEnrichmentWorkflow

Deletes an enrichment from the database:

**Steps:**

1. Execute `delete_enrichment` Activity with enrichment ID
2. Send SSE progress updates

### DeepResearchWorkflow

**Status:** Implementation pending. This workflow is planned for deep research functionality
but is not currently in use.

### EvaluationWorkflow

Evaluates AI responses using RAGAS metrics (Faithfulness, Response Relevancy) and
records scores to Langfuse. Started by the Agent service in fire-and-forget mode.

**Architecture:**

```text
┌─────────────────┐     start_workflow      ┌──────────────────┐
│  Agent Service  │ ──────────────────────► │  Temporal Server │
│  (dialogue.py,  │   (fire-and-forget)     │                  │
│   research.py)  │                         └────────┬─────────┘
└─────────────────┘                                  │
                                                     │ Execute
                                                     ▼
                                            ┌──────────────────┐
                                            │  Worker          │
                                            │  evaluate_ragas  │
                                            │  Activity        │
                                            └────────┬─────────┘
                                                     │
                                     ┌───────────────┼───────────────┐
                                     │               │               │
                                     ▼               ▼               ▼
                              ┌───────────┐  ┌───────────┐  ┌───────────┐
                              │ RAGAS LLM │  │ FastEmbed │  │ Langfuse  │
                              │ Evaluation│  │ Embedding │  │ Score API │
                              └───────────┘  └───────────┘  └───────────┘
```

**Input:**

- `trace_id`: Langfuse trace ID to attach scores to
- `mode`: Agent mode (`"dialogue"` or `"research"`)
- `question`: User's question
- `contexts`: Retrieved context documents
- `answer`: Generated answer

**Steps:**

1. Compute RAGAS metrics via `evaluate_ragas` Activity:
   - **Faithfulness**: Measures factual consistency of the answer with retrieved contexts
   - **Response Relevancy**: Measures how well the answer addresses the question
2. Record scores to Langfuse via `langfuse.create_score()`
3. Return scores and success status

**Metrics:**

| Metric             | Description                           | Range     |
| ------------------ | ------------------------------------- | --------- |
| `faithfulness`     | Answer grounded in retrieved contexts | 0.0 - 1.0 |
| `answer_relevancy` | Answer addresses the question         | 0.0 - 1.0 |

**Error Handling:**

The activity raises exceptions on failure (does not catch and return `success=False`).
This ensures Temporal marks the workflow as **Failed** and applies retry policies:

- Maximum attempts: 2
- Initial interval: 5 seconds

**Environment Variables (Helm configurable):**

| Variable                     | Description               | Used By |
| ---------------------------- | ------------------------- | ------- |
| `AI_EVALUATION_ENABLED`      | Enable/disable evaluation | Agent   |
| `EVALUATION_EMBEDDING_MODEL` | Embedding model for RAGAS | Worker  |
| `LANGFUSE_PUBLIC_KEY`        | Langfuse public key       | Worker  |
| `LANGFUSE_SECRET_KEY`        | Langfuse secret key       | Worker  |
| `LANGFUSE_HOST`              | Langfuse host URL         | Worker  |

**Agent Integration:**

The Agent service starts the workflow after generating a response:

```python
# agents/dialogue.py, agents/research.py
if settings.ai_evaluation_enabled and query and contexts and final_answer:
    from buun_curator_agent.temporal import start_evaluation_workflow

    workflow_id = await start_evaluation_workflow(
        trace_id=trace_id,
        mode="dialogue",  # or "research"
        question=query,
        contexts=contexts,
        answer=final_answer,
    )
```

The `start_evaluation_workflow` function uses fire-and-forget mode (`start_workflow`),
so the Agent returns immediately without waiting for evaluation to complete.

### SummarizationEvaluationWorkflow

Evaluates content summarization quality using RAGAS metrics and records scores to Langfuse.
Started by `ContentDistillationWorkflow` in fire-and-forget mode.

**Input:**

- `trace_id`: Batch trace ID for backward compatibility
- `items`: List of `SummarizationEvaluationItem` containing:
    - `entry_id`: Entry ID
    - `original_content`: Original content before summarization
    - `summary`: Generated summary
    - `trace_id`: Per-entry trace ID for Langfuse correlation
- `max_samples`: Maximum items to evaluate (default: 5)

**Steps:**

1. Convert workflow items to activity items
2. Execute `evaluate_summarization` Activity:
   - Compute RAGAS metrics (Faithfulness, Response Relevancy) for each item
   - Record scores to Langfuse using per-entry trace_id
3. Return average scores and evaluation count

**Per-Entry Trace ID:** Each item has its own `trace_id` generated deterministically from
`entry_id` and `batch_trace_id`. This allows Langfuse to correlate evaluation scores with
the original distillation LLM calls for each entry.

**Caller:** Started by `ContentDistillationWorkflow` when `AI_EVALUATION_ENABLED=true`.

### EmbeddingBackfillWorkflow

Computes embeddings for entries that have content but no embedding. Uses FastEmbed
with a multilingual model for CPU-efficient inference.

**Input:**

- `batch_size`: Number of entries to process per batch (default: 100)

**Steps:**

1. Fetch entries needing embeddings via `get_entries_for_embedding` Activity
   - Queries entries with `filteredContent` or `summary` present but `embedding=NULL`
   - Uses cursor-based pagination for large datasets
2. For each batch:
   - Fetch entry content via API
   - Compute embeddings using FastEmbed
   - Save embeddings via `/api/entries/embeddings` endpoint
3. Continue until all entries are processed
4. Return statistics (total, computed, saved counts)

**Content Priority:**

When computing embeddings: `filteredContent` → `summary` → `title`

**CLI Usage:**

```bash
# Compute embeddings for all entries without them
uv run trigger embedding-backfill

# With custom batch size
uv run trigger embedding-backfill --batch-size 200
```

**Use Cases:**

- Initial population after enabling recommendations
- Backfill after adding new entries via ingestion
- Recovery after database migration

**Embedding Storage:**

Embeddings are stored in the `entries.embedding` column as `vector(768)` using
pgvector. The column is created via Drizzle migration.

## Activity Pattern

All activities follow Temporal best practice of using a single Pydantic model argument:

```python
from pydantic import BaseModel, Field

class FetchContentsInput(BaseModel):
    """Input for fetch_contents activity."""
    entries: list[dict]
    timeout: int = 60
    concurrency: int = 3

class FetchContentsOutput(BaseModel):
    """Output from fetch_contents activity."""
    contents_for_distill: dict[str, dict] = Field(default_factory=dict)

@activity.defn
async def fetch_contents(input: FetchContentsInput) -> FetchContentsOutput:
    ...
```

Input/Output models are defined in `buun_curator/models/activity_io.py`.

## Data Models: Pydantic

This project uses Pydantic `BaseModel` for all Temporal I/O and API communication.

### Model Selection Policy

| Context                   | Model Type                  | Reason                               | Example                    |
| ------------------------- | --------------------------- | ------------------------------------ | -------------------------- |
| **Workflow I/O**          | Pydantic (`CamelCaseModel`) | camelCase for Next.js                | `SingleFeedIngestionInput` |
| **Activity I/O**          | Pydantic (`BaseModel`)      | Validation, consistent serialization | `FetchContentsInput`       |
| **API communication**     | Pydantic (`CamelCaseModel`) | camelCase conversion, validation     | `ProgressPayload` (SSE)    |
| **LLM structured output** | Pydantic                    | LangChain integration                | `EntryContext`             |
| **Models with Enum**      | Pydantic                    | Proper enum serialization            | `EntityInfo`               |

### Workflow I/O: Use Pydantic (CamelCaseModel)

Workflow input/output uses Pydantic with `CamelCaseModel` for automatic camelCase JSON serialization.
This allows Next.js to receive data in camelCase format directly from Temporal.

```python
# models/base.py
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class CamelCaseModel(BaseModel):
    """Base model with camelCase JSON serialization."""
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

# models/workflow_io.py
class SingleFeedIngestionInput(CamelCaseModel):
    """Input for SingleFeedIngestionWorkflow."""
    feed_id: str
    enable_content_fetch: bool = True
    auto_distill: bool = False
```

The `pydantic_data_converter` automatically uses `pydantic_core.to_json()` which respects aliases,
so workflow results are serialized with camelCase field names.

### Activity I/O: Use Pydantic (BaseModel)

Activity input/output uses Pydantic `BaseModel` for validation and consistent serialization.
Activities are internal to the worker, so camelCase conversion is not needed.

```python
# models/activity_io.py
from pydantic import BaseModel, Field

class FetchContentsInput(BaseModel):
    """Input for fetch_contents activity."""
    entries: list[dict]
    timeout: int = 60

class FetchContentsOutput(BaseModel):
    """Output from fetch_contents activity."""
    contents_for_distill: dict[str, dict] = Field(default_factory=dict)
    success_count: int = 0
    failed_count: int = 0
```

### API Communication: Use Pydantic

External API communication (REST, SSE, WebSocket) uses Pydantic for:

- Automatic camelCase conversion via `alias_generator`
- Built-in validation
- `model_dump(by_alias=True)` for JSON output

```python
# models/sse_events.py
class ProgressPayload(CamelCaseModel):
    """SSE event payload for workflow progress."""
    workflow_id: str
    workflow_type: str
    progress: int
    message: str

# Usage
payload = ProgressPayload(workflow_id="wf-123", progress=50, message="...")
json_data = payload.model_dump(by_alias=True)
# {"workflowId": "wf-123", "workflowType": "...", "progress": 50, "message": "..."}
```

### Why Pydantic for Enums?

Python's `str, Enum` types serialize incorrectly with standard JSON serialization:

```python
# Problem: str, Enum becomes character list when serialized
class Category(str, Enum):
    NEWS = "news"

@dataclass
class Entry:
    category: Category  # Serializes as ['n', 'e', 'w', 's'] ❌
```

Pydantic with `use_enum_values=True` solves this:

```python
class Entry(BaseModel):
    model_config = ConfigDict(use_enum_values=True)
    category: Category  # Serializes as "news" ✓
```

### Temporal Client Configuration

The worker uses `pydantic_data_converter` for proper Pydantic v2 support:

```python
# buun_curator/temporal.py
from temporalio.contrib.pydantic import pydantic_data_converter

async def get_temporal_client() -> Client:
    return await Client.connect(
        config.temporal_host,
        namespace=config.temporal_namespace,
        data_converter=pydantic_data_converter,
    )
```

This converter handles Pydantic models for all Temporal I/O.

### Summary

1. **Workflow I/O**: Use Pydantic `CamelCaseModel` (camelCase for Next.js)
2. **Activity I/O**: Use Pydantic `BaseModel` (validation, internal to worker)
3. **API/External**: Use Pydantic `CamelCaseModel` (camelCase, validation)
4. **LLM output**: Use Pydantic (LangChain integration)
5. **With Enums**: Use Pydantic (proper serialization)

## Testing

### Test Structure

```text
tests/
├── conftest.py              # Shared fixtures (LLM output fixtures)
├── fixtures/
│   ├── html/                # HTML fixtures for integration tests
│   │   ├── article_clean.html
│   │   ├── article_with_ads.html
│   │   └── article_with_custom_elements.html
│   └── *.txt                # Text fixtures for unit tests
├── activities/              # Activity unit tests
│   ├── conftest.py          # Activity-specific fixtures
│   └── test_fetch.py
├── services/                # Service unit tests
│   ├── conftest.py          # Service-specific fixtures
│   └── test_content.py
├── integration/             # Integration tests (real Crawl4AI)
│   ├── conftest.py          # Integration fixtures & pytest options
│   └── test_content_fetch.py
└── test_summarizer.py
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run unit tests only (fast, excludes integration)
uv run pytest -m "not integration"

# Run integration tests only
uv run pytest -m integration

# Run specific test file
uv run pytest tests/services/test_content.py

# Verbose output
uv run pytest -v
```

### Integration Tests

Integration tests use real Crawl4AI to verify HTML extraction behavior.
They are marked with `@pytest.mark.integration`.

```bash
# Run integration tests
uv run pytest tests/integration/ -v

# Show extracted markdown output (useful for debugging)
uv run pytest tests/integration/ --show-markdown -s

# Run specific test with markdown output
uv run pytest tests/integration/test_content_fetch.py::test_fetch_clean_article --show-markdown -s
```

The `--show-markdown` option displays the extracted markdown content for each test,
which is helpful when debugging extraction rules or verifying Crawl4AI behavior.

## Worker Health Check and Recovery

The worker includes an HTTP health check server that verifies Temporal connectivity.
Kubernetes uses this to automatically restart the worker if the Temporal connection
becomes unhealthy.

### Health Check Endpoints

| Endpoint  | Purpose                               | Probe Type |
| --------- | ------------------------------------- | ---------- |
| `/health` | Verify Temporal connectivity          | Liveness   |
| `/ready`  | Check if server is accepting requests | Readiness  |

The `/health` endpoint calls Temporal's `DescribeNamespace` API to verify the gRPC
connection is functional. If the SDK Core has panicked or the connection is broken,
this check will fail.

### Kubernetes Probes Configuration

The worker deployment includes liveness and readiness probes configurable via Helm values:

```yaml
# values.yaml
worker:
  healthPort: 8080

  livenessProbe:
    httpGet:
      path: /health
      port: health
    initialDelaySeconds: 30
    periodSeconds: 30
    timeoutSeconds: 10
    failureThreshold: 3

  readinessProbe:
    httpGet:
      path: /ready
      port: health
    initialDelaySeconds: 10
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 3
```

To disable health probes (not recommended for production):

```yaml
worker:
  healthPort: ""
  livenessProbe: ""
  readinessProbe: ""
```

With the default configuration:

- Worker has 30 seconds to start before health checks begin
- Health is checked every 30 seconds
- After 3 consecutive failures (90 seconds total), the pod is restarted

### Environment Variables

| Variable                          | Description                         | Default         |
| --------------------------------- | ----------------------------------- | --------------- |
| `HEALTH_PORT`                     | Port for health check server        | `8080`          |
| `MAX_CONCURRENT_ACTIVITIES`       | Maximum concurrent activity tasks   | `0` (unlimited) |
| `MAX_CONCURRENT_WORKFLOW_TASKS`   | Maximum concurrent workflow tasks   | `0` (unlimited) |
| `MAX_CONCURRENT_LOCAL_ACTIVITIES` | Maximum concurrent local activities | `0` (unlimited) |

### Worker Concurrency Configuration

The worker supports configurable concurrency limits to prevent resource exhaustion
when running multiple workflows and activities simultaneously.

```yaml
# values.yaml
worker:
  concurrency:
    # Max concurrent activity tasks (recommended: 10-20 for stability)
    maxActivities: 10
    # Max concurrent workflow tasks (0 = Temporal default)
    maxWorkflowTasks: 0
    # Max concurrent local activities (0 = Temporal default)
    maxLocalActivities: 0
```

**Recommended Settings:**

- `maxActivities: 10` - Limits concurrent activities to prevent API connection
  exhaustion and memory pressure from activities like embedding computation
- `maxWorkflowTasks: 0` - Use Temporal default (usually sufficient)
- `maxLocalActivities: 0` - Use Temporal default

Setting `maxActivities` helps prevent issues when heavy workflows like
`EmbeddingBackfillWorkflow` and `AllFeedsIngestionWorkflow` run concurrently.

### Troubleshooting: Worker Loses Temporal Connection

**Symptoms:**

- Temporal UI shows "No workers running"
- Worker pod shows "Running" in `kubectl get pods`
- Workflows stuck in "Running" state without progress

**Root Cause:**

This can occur when the Temporal SDK Core (Rust) panics due to a race condition
when handling concurrent workflow activations. The Python process stays alive
but stops polling Temporal for work.

**Resolution:**

With health probes configured, Kubernetes will automatically restart the pod after
detecting health check failures. For manual recovery:

```bash
kubectl rollout restart deployment/buun-curator-worker
```

**Prevention:**

- Configure `worker.concurrency.maxActivities: 10` to limit concurrent activities
- Use httpx connection pool limits (built-in to APIClient)
- Health probes ensure automatic recovery within 90 seconds of connection loss
