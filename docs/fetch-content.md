# Content Extraction Specification

This document describes how entry content is fetched and filtered using Crawl4AI, including how Feed-specific extraction rules are stored and applied.

## Overview

The content extraction pipeline:

1. **Feed Ingestion Workflow** triggers content fetching for new entries
2. **ContentFetcher** uses Crawl4AI to extract entry content
3. **Excluded selectors** (default + Feed-specific) remove unwanted elements
4. **Chat UI** allows users to preview and save new extraction rules

## Feed Extraction Rules Storage

Extraction rules are stored in the `feeds.options` JSON column as an array of `ExtractionRule` objects.

### Type Definitions

- `ExtractionRule` interface (`type`, `value`, `description`, `createdAt`)
- `FeedOptions` interface (`extractionRules`)

### Example Feed.options

```json
{
  "fetchLimit": 10,
  "extractionRules": [
    {
      "type": "css_selector",
      "value": ".related-articles",
      "description": "Remove related articles section",
      "createdAt": "2024-12-09T10:30:00Z"
    }
  ]
}
```

## Content Fetching Pipeline

```text
FeedIngestionWorkflow
    │
    ├── crawl_feeds_activity     # Fetch RSS/Atom feeds, create entries
    │       ↓
    ├── fetch_contents_activity  # Fetch full entry content
    │       │
    │       └── ContentFetcher.fetch()  ← extraction_rules passed here
    │               ↓
    └── process_entry_content Activity (optional)
```

### How Extraction Rules Are Applied

1. **Default selectors**: `ContentFetcher` has built-in `DEFAULT_EXCLUDED_SELECTORS` for common ads/noise
2. **Feed-specific rules**: CSS selectors from `Feed.options.extractionRules` are appended
3. **Combined selector**: All selectors are joined with `,` and passed to Crawl4AI's `excluded_selector` parameter
4. **DOM filtering**: Crawl4AI removes matching elements before extracting content

## Crawl4AI Filtering Pipeline

The content extraction uses a multi-level filtering pipeline:

```text
HTML Document
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. HTML Pre-processing (Rule-based)                         │
│    ├── excluded_tags: nav, header, footer, aside, form, ... │
│    └── excluded_selector: CSS selectors (ads, sidebars)     │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. ImagePreservingFilter (Heuristic-based)                  │
│    Extends PruningContentFilter to preserve images.         │
│    Scores each text block by:                               │
│    - Text density (text vs HTML ratio)                      │
│    - Link density (links vs text ratio)                     │
│    - Tag importance (article > p > aside)                   │
│    Always preserves: figure, img, picture, video, audio     │
│    Removes blocks below threshold (0.3, dynamic)            │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Markdown Generation                                      │
│    ├── raw_markdown: All content after step 1               │
│    └── fit_markdown: Filtered content after step 2          │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Content Selection                                        │
│    Choose between raw_markdown and fit_markdown             │
│    (see "Content Selection Logic" below)                    │
└─────────────────────────────────────────────────────────────┘
```

### Processing Order

1. **Rule-based filtering first**: `excluded_tags` and `excluded_selector` are applied to HTML before any content analysis
2. **ImagePreservingFilter second**: Operates on the pre-cleaned HTML, preserving image elements
3. **Markdown output**: Both `raw_markdown` and `fit_markdown` are generated
4. **Content selection**: Choose the best content based on length thresholds

This design ensures:

- Explicit rules (ads, navigation) are reliably removed
- ImagePreservingFilter focuses on content quality while keeping images
- Fallback to raw content when filtering is too aggressive

## ImagePreservingFilter

`ImagePreservingFilter` extends Crawl4AI's `PruningContentFilter` to preserve media elements that would otherwise be pruned.

### Preserved Tags

- `figure`, `img`, `picture` - Images and figures
- `video`, `audio` - Media elements
- `figcaption` - Image captions

### How It Works

1. Nodes containing these tags are never pruned, regardless of score
2. Tag weights are increased for image-related elements (figure: 1.5, picture: 1.3)
3. Standard pruning logic applies to all other content

### Filter Settings

| Setting | Value | Description |
|---------|-------|-------------|
| `threshold` | 0.3 | Score threshold for content blocks |
| `threshold_type` | dynamic | Adjusts threshold based on tag importance |
| `min_word_threshold` | None | Disabled to preserve code blocks |

## Content Selection Logic

After Crawl4AI generates both `raw_markdown` and `fit_markdown`, the system selects the best content for `full_content`.

### Selection Algorithm

```python
MIN_CONTENT_LENGTH = 500  # Minimum chars for filtered content

use_filtered = (
    len(fit_markdown) >= MIN_CONTENT_LENGTH
    and len(fit_markdown) >= len(raw_markdown) * 0.1
)

if use_filtered:
    full_content = fit_markdown
else:
    full_content = raw_markdown  # Fallback
```

### Decision Flow

```text
Evaluate fit_markdown
    │
    ├─ Less than 500 chars? → Use raw_markdown
    │
    ├─ Less than 10% of raw_markdown? → Use raw_markdown
    │   (Detects over-aggressive filtering)
    │
    └─ Both conditions pass → Use fit_markdown
```

### Why 10% Threshold?

Some pages cause `ImagePreservingFilter` to be overly aggressive, extracting only titles or headers while discarding the article body. The 10% threshold detects this by comparing filtered vs raw content length:

| Scenario | raw_markdown | fit_markdown | 10% threshold | Result |
|----------|--------------|--------------|---------------|--------|
| Normal filtering | 6000 chars | 4000 chars | 600 | fit_markdown ✓ |
| Over-filtering | 6000 chars | 103 chars | 600 | raw_markdown (fallback) |
| Short article | 800 chars | 500 chars | 80 | fit_markdown ✓ |

## FetchedContent Output

The `ContentFetcher.fetch()` method returns a `FetchedContent` dataclass:

```python
@dataclass
class FetchedContent:
    full_content: str           # Selected markdown (fit or raw)
    raw_html: str = ""          # Original HTML for rule creation
    screenshot: bytes | None    # PNG screenshot (for thumbnails)
    title: str = ""             # HTML page title from metadata
```

| Field | Description |
|-------|-------------|
| `full_content` | Final markdown content (fit_markdown or raw_markdown based on selection logic) |
| `raw_html` | Original HTML, used for creating extraction rules in the UI |
| `screenshot` | Page screenshot for thumbnail generation (when enabled) |
| `title` | Page title from HTML `<title>` or og:title meta tag |
