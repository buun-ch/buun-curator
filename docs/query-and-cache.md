# React Query Cache Design

This document describes TanStack Query (React Query) cache keys and
query flows corresponding to UI actions.

## Query Keys

| Query Key | Type | Hook | staleTime | Description |
|-----------|------|------|-----------|-------------|
| `["subscriptions", filterMode]` | Query | `useSubscriptions` | default | Subscription tree with unread counts |
| `["entries", subscription, filterMode, sortMode]` | InfiniteQuery | `useEntries` | default | Entry list with pagination (lightweight `EntryListItem`) |
| `["entry", entryId]` | Query | `useEntry` | 30s | Single entry with full content and labels |
| `["search", query, subscription]` | Query | `useEntrySearch` | 30s | Search results (Meilisearch) |
| `["feed", feedId]` | Query | `useSelectedSubscriptionInfo` | default | Feed detail information |
| `["reddit-favorites"]` | Query | `useRedditFavorites` | 5 min | Favorite subreddits |
| `["subreddit", name]` | Query | `useSubreddit` | 10 min | Subreddit information |
| `["subreddit-posts", name, sort, time, limit]` | InfiniteQuery | `useSubredditPosts` | 1 min | Subreddit post list |
| `["reddit-post", postId]` | Query | `useRedditPost` | 1 min | Reddit post detail |

## Data Architecture

### Entry Types

Two data types are used for entries to optimize performance:

| Type | Query Key | Usage | Fields |
|------|-----------|-------|--------|
| `EntryListItem` | `["entries", ...]` | Content List | id, title, summary, feedName, isRead, isStarred, keep, etc. |
| `Entry` | `["entry", entryId]` | Content Viewer | Extends `EntryListItem` with fullContent, translatedContent, labels, etc. |

This separation ensures the entry list query doesn't include heavy content
fields, improving list loading performance.

### Cache Relationship

```text
Content List                          Content Viewer
     │                                      │
     ▼                                      ▼
["entries", sub, filter, sort]       ["entry", entryId]
     │                                      │
     ▼                                      ▼
EntryListItem[]                         Entry
(lightweight)                      (full content)
```

## UI Action → Query Flows

### Fetch new entries from subscription sidebar

Fetches new entries from all feeds via the refresh button in the sidebar.

```text
User Action: Click refresh button in sidebar
    │
    ├─ Hook: useFeedIngestion
    │
    ├─ onStart callback
    │   └─ Invalidate: ["subscriptions"] (prefix)
    │   └─ Refetch: current subscriptions query
    │
    ├─ Workflow: AllFeedsIngestionWorkflow
    │   └─ API: POST /api/workflows/ingest
    │   └─ Poll: GET /api/workflows/{id}/status (2s interval, max 5 min)
    │
    └─ onComplete callback
        └─ Invalidate: ["subscriptions"] (prefix)
        └─ Refetch: current subscriptions query
```

### Refetch from content list (single feed)

Refetches entries from a single feed via the refresh button in the content list header.
Only available when a feed is selected.

```text
User Action: Click refresh button in content list header
    │
    ├─ Hook: useSingleFeedIngestion
    │
    ├─ Workflow: SingleFeedIngestionWorkflow
    │   └─ API: POST /api/workflows/ingest-feed
    │   └─ Body: { feedId, feedName, feedUrl, ... }
    │   └─ Poll: GET /api/workflows/{id}/status (2s interval, max 5 min)
    │
    └─ onComplete callback
        └─ Invalidate: ["subscriptions"] (prefix)
        └─ Refetch: subscriptions query
        └─ Invalidate: ["entries"] (prefix)
        └─ Refetch: entries query
```

### Refetch entry from content viewer

Refetches entry content via the refresh button in the content viewer.
Uses a Temporal workflow to re-fetch content.

```text
User Action: Click refresh button in content viewer
    │
    ├─ Hook: useEntryActions.refreshEntry
    │
    ├─ Step 1: Trigger Temporal workflow
    │   └─ API: POST /api/entries/{id}/refetch
    │   │
    │   ├─ If cleared (fetchContent: false):
    │   │   └─ Invalidate: ["entry", entryId]
    │   │   └─ Return early
    │   │
    │   └─ If workflow started:
    │       └─ SSE handles progress updates
    │
    └─ Step 2: On workflow completion (via SSE)
        └─ handleEntryUpdated callback
        └─ Invalidate: ["entry", entryId]
        └─ Invalidate: ["entries"] with refetchType: "none"
```

**Note:** The list is NOT refetched after invalidation (`refetchType: "none"`).
This marks the cache as stale for future refetch while preserving the current
display (important when in Unread mode since the entry is now read).

### Translation

Fetches translated content when switching to translation mode.

```text
User Action: Switch to "translated" or "both" mode
    │
    ├─ Hook: useTranslation
    │
    ├─ Check: hasTranslation already?
    │   └─ If yes: No workflow triggered
    │   └─ If no: Continue below
    │
    ├─ Auto-trigger (via useEffect) or manual trigger
    │   └─ API: POST /api/entries/{id}/translate
    │   └─ Returns: { workflowId }
    │
    ├─ Poll for completion
    │   └─ API: GET /api/entries/{id}/translate?workflowId={id}
    │   └─ Interval: 2s
    │
    └─ onTranslationComplete callback
        └─ Invalidate: ["entry", entryId]
        └─ TanStack Query refetches entry with translatedContent
```

**Cache impact:**

- `["entry", entryId]` is invalidated and refetched
- Entry list doesn't display translation status, so no update needed

### Select entry (mark as read)

Automatically marks the entry as read when selected. Uses TanStack Query
for data fetching.

```text
User Action: Click entry in list
    │
    ├─ Hook: useSelectedEntry
    │   └─ Sets: selectedEntryId state
    │
    ├─ Hook: useEntry(selectedEntryId)
    │   └─ Query Key: ["entry", entryId]
    │   └─ TanStack Query fetches entry data
    │
    ├─ If entry loaded and not already read:
    │   └─ API: PATCH /api/entries/{id} { isRead: true }
    │   └─ setQueryData: ["entry", entryId] (update isRead)
    │   └─ Update: entries list (setEntries)
    │   └─ Callback: onMarkAsRead → updateCountOnRead
    │       └─ setQueryData: ["subscriptions", filterMode] (count -1)
    │   └─ Invalidate: ["entries"] with refetchType: "none"
    │
    └─ Return: selectedEntry from query cache
```

### Toggle star/read/keep status

Toggles the star, read, or keep status of an entry.

```text
User Action: Click star/read/keep toggle button
    │
    ├─ Hook: useEntryActions.toggleStar / toggleRead / toggleKeep
    │
    ├─ Optimistic update:
    │   └─ Update: entries list (setEntries)
    │   └─ Update: entry cache via setSelectedEntry
    │       └─ setQueryData: ["entry", entryId]
    │   └─ For toggleRead: Callback → updateCountOnToggleRead
    │       └─ setQueryData: ["subscriptions", filterMode]
    │
    ├─ API: PATCH /api/entries/{id}
    │
    ├─ For toggleRead only:
    │   └─ Invalidate: ["entries"] with refetchType: "none"
    │
    └─ On error: Revert optimistic updates
```

### Add label to entry

Adds a label to an entry. Automatically sets `keep: true`.

```text
User Action: Add label via Tagify input
    │
    ├─ Hook: useEntryLabels.addLabel
    │
    ├─ API: POST /api/entries/{id}/labels
    │   └─ Body: { labelId }
    │   └─ Server: Also sets entry.keep = true
    │
    └─ onSuccess:
        └─ Invalidate: ["entry", entryId]
        └─ TanStack Query refetches entry with updated labels and keep status
```

**Note:** No callback chain needed. The query invalidation in `useEntryLabels`
triggers automatic refetch of `["entry", entryId]`, updating the Content Viewer.

### Mark all as read

Marks all entries in the current view as read.

```text
User Action: Click "Mark all as read" button
    │
    ├─ Hook: useEntries.markAllAsRead
    │
    ├─ API: POST /api/entries/mark-all-read
    │   └─ Body: { feedId? } or { categoryId? } or {}
    │
    ├─ Invalidate: ["entries", selectedSubscription] (prefix)
    │   └─ Triggers refetch of current query
    │
    └─ Invalidate: ["subscriptions"] (prefix)
        └─ Triggers refetch of counts
```

### Search entries

Searches entries using Meilisearch when filter mode is "search".

```text
User Action: Select "Search" filter mode and type query
    │
    ├─ Component: ReaderContent
    │   └─ State: filterMode === "search"
    │
    ├─ Hook: useEntrySearch
    │   └─ Debounce: 300ms
    │   └─ Query Key: ["search", debouncedQuery, selectedSubscription]
    │
    ├─ Display Logic:
    │   ├─ Search mode + query present → Show search results
    │   ├─ Search mode + no query → Show empty list
    │   └─ Other modes → Show useEntries results
    │
    └─ API: GET /api/search?q={query}&feedId={feedId}
        └─ Backend: Meilisearch full-text search
        └─ Response: { entries, totalCount, processingTimeMs }
```

**Note:** In search mode, `useEntries` still runs but its results are not displayed.
The search results include highlighting information (`_highlighted.title`,
`_highlighted.summary`) for displaying matched terms.

## Cache Update Patterns

### Optimistic Updates

Uses `setQueryData` for immediate UI updates:

- Entry isStarred, isRead, keep updates (both list and entry cache)
- Subscription unread count updates

Rolls back to original state on error.

### Query Invalidation

Uses `invalidateQueries` to trigger refetch:

```typescript
// Invalidate and refetch immediately (active queries)
await queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
```

Use cases:

- After label addition (refetch entry with updated labels and keep status)
- After translation completion (refetch entry with translatedContent)
- After workflow completion (refetch entry with updated content)

### Stale Marking (refetchType: "none")

Marks other queries as stale while maintaining current display:

```typescript
await queryClient.invalidateQueries({
  queryKey: ["entries"],
  refetchType: "none",
});
```

Use cases:

- After marking an entry as read, ensures fresh data when switching to other subscriptions
- Maintains current list display while invalidating cache in the background

### Cascade Invalidations

Invalidates related caches in sequence:

```text
Entry read status change
    └─ Mark ["entries"] as stale
    └─ Invalidate ["subscriptions"] (count update)
```

## Helper Functions

### invalidateSubscriptions

Invalidates subscription cache after feed/category CRUD operations:

```typescript
import { invalidateSubscriptions } from "@/hooks/use-subscriptions";

// Usage in settings components
await invalidateSubscriptions(queryClient);
```

## Key Hooks

| Hook | Purpose | Query Key Used |
|------|---------|----------------|
| `useEntry` | Fetch single entry with full content | `["entry", entryId]` |
| `useEntries` | Fetch entry list (lightweight) | `["entries", ...]` |
| `useSelectedEntry` | Manage selected entry state, uses `useEntry` internally | `["entry", entryId]` |
| `useEntryActions` | Toggle star/read/keep, refresh entry | Updates both caches |
| `useEntryLabels` | Add/remove labels | Invalidates `["entry", entryId]` |
