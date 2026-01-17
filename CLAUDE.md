# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

For project overview and setup instructions, see [README.md](./README.md).
For technical documentation, see [Documentation](./README.md#documentation) section in README.md.

## Terminology

For all terminology, see [docs/terminology.md](docs/terminology.md).

Key terms: **Entry** (not "Article"), **Feed**, **Category**, **Subscription**.

## Commands

**Working Directories and Environment Setup:**

- **Frontend (TypeScript/JavaScript):** Run commands from project root (`/`)
- **Worker (Python/Temporal):** Run commands from `worker/` after activating venv:

  ```bash
  cd worker
  source .venv/bin/activate
  ```

- **Agent (Python/LangGraph):** Run commands from `agent/` after activating venv:

  ```bash
  cd agent
  source .venv/bin/activate
  ```

**Development:**

```bash
bun dev                               # Start dev server with Turbopack (http://localhost:3000)
op run --env-file=.env.op -- bun dev  # With 1Password secrets
```

**Build & Production:**

```bash
bun build  # Production build
bun start  # Start production server
```

**Code Quality (TypeScript/JavaScript):**

```bash
bun check         # ESLint + TypeScript type check
bun lint .        # ESLint only
bun typecheck     # TypeScript type check only
bun prettier      # Check formatting
bun prettier:fix  # Fix formatting
```

After writing or modifying TypeScript/JavaScript code, always run `bun check` to verify the code.

**Code Quality (Python - worker/):**

```bash
cd worker
uv run ruff check .   # Linting
uv run ruff format .  # Formatting
uv run pyright        # Type checking
```

After writing or modifying Python code in `worker/`, always run `ruff check` and `pyright` to verify the code.

**Worker (Temporal Worker/CLI):**

```bash
cd worker
op run --env-file=.env.op -- uv run worker    # Start Temporal worker
op run --env-file=.env.op -- uv run trigger ingest  # Trigger feed ingestion
op run --env-file=.env.op -- uv run schedule show   # Show schedule status
```

If commands fail, verify that `worker/.venv` is activated.

**Python String Formatting:** When strings exceed the line length limit, use implicit string concatenation:

```python
# Before (too long)
logger.info(f"Processing {count} entries (fetch={fetch}, summarize={summarize})")

# After (split across lines)
logger.info(
    f"Processing {count} entries "
    f"(fetch={fetch}, summarize={summarize})"
)
```

**Python Logging (Worker):**

| Location | Logger | Syntax |
| -------- | ------ | ------ |
| **Workflows** | `workflow.logger` | `workflow.logger.info("msg", extra={"key": value})` |
| **Activities/Services** | `structlog` (`get_logger()`) | `logger.info("msg", key=value)` |

`workflow.logger` is a standard Python logger (does NOT support kwargs) while structlog does.
See [docs/logs-and-tracing.md](docs/logs-and-tracing.md) for details.

## Git Operations

**Do not operate git without explicit instruction from the user.** This includes:

- `git add`, `git commit`, `git push`
- `git checkout`, `git branch`, `git merge`
- Any other git commands that modify the repository state

Wait for explicit user requests before performing any git operations.

## Documentation Comments

**TypeScript (TSDoc format):**

Use third-person declarative style ("Converts...", "Returns..."). Types are inferred from TypeScript, so don't duplicate them in `@param` tags.

```typescript
/**
 * Normalizes an Entry by populating computed fields.
 *
 * @param entry - The entry from the database
 * @returns Entry with computed fields populated
 */
export function normalizeEntry(entry: Entry): Entry {
```

For interfaces and types, use `/** ... */` comments:

```typescript
/** Options for the useEntries hook. */
interface UseEntriesOptions {
  /** The subscription ID to fetch entries for. */
  selectedSubscription: string;
  /** Filter mode for entries (all, unread, starred). */
  filterMode: FilterMode;
}
```

For module-level documentation, add a module docstring at the top:

```typescript
/**
 * Hook for managing entry list data and infinite scroll.
 *
 * @module hooks/use-entries
 */
```

**Python (NumPyDoc format):**

Use imperative style ("Convert...", "Return...") per PEP 257. Add a newline after the opening `"""`:

```python
def fetch(self, url: str, title: str | None = None) -> FetchedContent:
    """
    Fetch entry content from URL and return as Markdown.

    Parameters
    ----------
    url : str
        The entry URL to fetch.
    title : str | None, optional
        Entry title to remove duplicate headings (default: None).

    Returns
    -------
    FetchedContent
        Content with full_content and filtered_content.
    """
```

For optional parameters, add `, optional` suffix and `(default: X)` in description.

For simple one-line docstrings (classes, short functions):

```python
class ContentFetcher:
    """Service for fetching full entry content."""
```

**Code Quality (Markdown):**

```bash
bun exec markdownlint-cli2 "**/*.md"  # Check all Markdown files
bun exec markdownlint-cli2 README.md  # Check specific file
```

After editing Markdown files, run `markdownlint-cli2` to verify formatting.

**Tool Management:** Uses mise for Bun 1.3.6. Run `mise install` if needed.

**Database Migrations (Drizzle):**

```bash
bun drizzle-kit generate  # Generate migration from schema changes
bun db:migrate            # Apply migrations to dev DB
bun db:migrate:test       # Apply migrations to test DB
```

**Migration workflow (MUST follow this order):**

1. Edit `db/schema.ts`
2. Run `bun drizzle-kit generate`
3. Rename the generated SQL file to a descriptive name (e.g., `0012_add_entry_preference.sql`)
4. Update `drizzle/meta/_journal.json`:
   - Change `tag` to match the new filename (without `.sql`)
   - **CRITICAL**: Ensure `when` timestamp is greater than the previous migration's `when`
5. Run `bun db:migrate` (dev DB)
6. Run `bun db:migrate:test` (test DB)
7. Verify both commands succeed without errors

**Common mistakes to avoid:**

- **NEVER** use MCP postgres tools or psql to directly add/modify columns. Always use migrations.
- **NEVER** skip running both `db:migrate` and `db:migrate:test`.
- If migration fails with "column already exists", it means the migration was partially applied. Check `drizzle.__drizzle_migrations` table.

**Manual migrations:** Drizzle may not detect all schema changes (e.g., foreign key `onDelete` options). In such cases:

1. Create SQL file manually in `drizzle/` with proper naming (e.g., `0013_description.sql`)
2. Add entry to `drizzle/meta/_journal.json` with next `idx`, correct `tag`, and `when` > previous migration

## Architecture

Buun Curator is a multi-panel feed reader with integrated AI assistant, built on Next.js 16 App Router.

### Layout Structure

The main UI (`app/reader-layout.tsx`) uses `react-resizable-panels` to create a 4-panel horizontal layout:

```text
┌─────────────┬─────────────────┬─────────────────────┬─────────────────┐
│ Subscription│   Content List  │   Content Viewer    │  AI Assistant   │
│   Sidebar   │  (entries,      │   (entry detail,    │   (chat UI,     │
│ (collapsible│   reddit posts) │    reddit posts)    │   toggleable)   │
│  hierarchy) │                 │                     │                 │
└─────────────┴─────────────────┴─────────────────────┴─────────────────┘
```

- **SubscriptionSidebar**: Hierarchical feed categories and Reddit sections (Search, Favorites), collapsible to icon-only
- **ContentList**: Displays different content based on mode:
    - Entries mode: Feed entries with thumbnails, unread indicators, star toggle
    - Reddit Search mode: Search results with votes, comments, subreddit info
    - Subreddit Info mode: Subreddit metadata (subscribers, description, etc.)
- **ContentViewer**: Full content display with navigation controls (for entries)
- **AssistantSidebar**: AI chat interface, can be toggled open/closed

### Key Directories

- `app/` - Next.js App Router pages and API routes
- `hooks/` - Custom React hooks for state management (subscriptions, entries, entry actions)
- `components/reader/` - Feed reader UI components (content-list, content-viewer, subscription-sidebar, assistant-sidebar, reddit-search-results, subreddit-info)
- `components/ui/` - shadcn/ui base components
- `lib/types.ts` - Shared TypeScript types and helper functions

### AI Integration

Chat API (`app/api/chat/route.ts`) uses:

- Vercel AI SDK with OpenAI provider
- Custom fetch middleware for LiteLLM/Langfuse tracing
- Configurable via `OPENAI_BASE_URL`, `OPENAI_MODEL` env vars

### State Management

This app uses three state management patterns, each for a specific purpose:

| Pattern | Location | Use Case | Persistence |
|---------|----------|----------|-------------|
| **Zustand** | `stores/settings-store.ts` | User preferences, UI state to persist | localStorage |
| **TanStack Query** | `hooks/use-*.ts` | Server data (fetch, cache, sync) | Memory (cache) |
| **useState** | Custom hooks, components | Temporary UI state | None |

**When to use each:**

- **Zustand** (`useSettingsStore`): For state that should persist across browser sessions
    - `selectedSubscription` - Currently selected feed/category
    - `assistantOpen` - AI sidebar open/close state
    - `feedFilterMode` - Entry filter (all/unread/starred)
    - `redditSearches` - Saved Reddit search queries
    - `subredditSettings` - Per-subreddit filter preferences

- **TanStack Query**: For server data that needs caching and synchronization
    - `useSubscriptions` - Feed/category tree with counts
    - `useEntries` - Entry list with infinite scroll
    - `useRedditFavorites` - Favorite subreddits (CRUD)
    - `useSubreddit`, `useSubredditPosts` - Reddit data

- **useState**: For ephemeral UI state within a session
    - `viewMode` - Reader vs settings view
    - `contentPanelMode` - Entries vs Reddit content
    - `subscriptionCollapsed` - Sidebar collapse state

**API endpoints:**

- `/api/subscriptions` - Subscription tree with unread counts
- `/api/entries` - Entry list with filtering (feedId, categoryId, starredOnly, unreadOnly)
- `/api/entries/[id]` - Entry detail with full content

Entry state uses optimistic updates for star/read status changes.

The AI chat uses CopilotKit (`@copilotkit/react-core`, `@copilotkit/react-ui`) with `CopilotKit` provider.

## Tech Stack

- **Framework:** Next.js 16 with Turbopack, React 19, TypeScript
- **Styling:** Tailwind CSS v4, shadcn/ui (New York style), CSS variables with OKLCH colors
- **AI:** CopilotKit, OpenAI
- **Layout:** react-resizable-panels for draggable panel boundaries
- **Animation:** Framer Motion
- **Icons:** Lucide React

## Python Data Models (worker/)

All Temporal I/O uses Pydantic:

| Context | Model Type | Reason |
|---------|------------|--------|
| **Workflow I/O** | Pydantic (`CamelCaseModel`) | camelCase for Next.js |
| **Activity I/O** | Pydantic (`BaseModel`) | Validation, consistent serialization |
| **API/External** | Pydantic (`CamelCaseModel`) | camelCase conversion, validation |
| **LLM output** | Pydantic | LangChain structured output |
| **With Enum** | Pydantic | Proper enum serialization |

```python
# Workflow I/O: Pydantic with CamelCaseModel
class SingleFeedIngestionInput(CamelCaseModel):
    feed_id: str  # → "feedId" in JSON
    enable_content_fetch: bool = True

# Activity I/O: Pydantic with BaseModel
class FetchContentsInput(BaseModel):
    entries: list[dict]
    timeout: int = 60
```
