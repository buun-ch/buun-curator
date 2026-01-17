# Context Extraction and Enrichment

This document specifies the context extraction and enrichment workflows in Buun Curator.

## Overview

Context extraction analyzes entry content to produce structured metadata including:

- **Classification**: Subject domain and content type
- **Entities**: People, organizations, software, etc.
- **Relationships**: Connections between entities
- **Key Points**: Main takeaways (3-5 items)
- **Extracted Links**: URLs found in the content

Enrichment augments extracted context with external data:

- **GitHub Enrichment**: Repository info for software entities (automatic)
- **Web Page Enrichment**: Content from linked URLs (user-triggered)

## Architecture

### Context Collection (Automatic)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                     ContextCollectionWorkflow                           │
│  (Orchestrates extraction and enrichment for multiple entries)          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│ ExtractEntry  │           │ ExtractEntry  │           │ ExtractEntry  │
│ ContextWF     │           │ ContextWF     │           │ ContextWF     │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐           ┌───────────────┐           ┌───────────────┐
│  LLM Context  │           │  LLM Context  │           │  LLM Context  │
│  Extraction   │           │  Extraction   │           │  Extraction   │
└───────────────┘           └───────────────┘           └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    ▼
                    ┌───────────────────────────┐
                    │  GitHub Enrichment Phase  │
                    │  (search/rerank/README)   │
                    └───────────────────────────┘
```

### Web Page Enrichment (User-Triggered)

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                          User Action                                    │
│  (Clicks "+" button on a link in Context Panel)                         │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     FetchEntryLinksWorkflow                             │
│  (Fetches content from selected URLs)                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  fetch_and_save_entry_    │
                    │  links Activity           │
                    │  (ContentFetcher + Save)  │
                    └───────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │  entry_enrichments table  │
                    │  (type: "web_page")       │
                    └───────────────────────────┘
```

## Workflows

### ExtractEntryContextWorkflow

Sub-workflow that extracts context from a single entry.

**Location**: `worker/buun_curator/workflows/extract_entry_context.py`

**Steps**:

1. **Fetch Entry**: Get entry data via `get_entry` activity
2. **Extract Content**: Get markdown content (tries `filteredContent` → `fullContent` → `feedContent`)
3. **LLM Extraction**: Extract structured context via `extract_entry_context` activity
4. **Save Context**: Persist to database via `save_entry_context` activity

**Input**:

```python
ExtractEntryContextInput(entry_id: str)
```

**Output**:

```python
EntryContext | None  # Returns None if entry not found or has no content
```

### ContextCollectionWorkflow

High-level workflow that orchestrates context extraction for multiple entries.

**Location**: `worker/buun_curator/workflows/context_collection.py`

**Steps**:

1. **Extract All Contexts**: Run ExtractEntryContextWorkflow for each entry
2. **Analyze Contexts**: Generate execution plan with statistics
3. **Collect Enrichment Candidates**: Identify software entities for GitHub enrichment
4. **Execute GitHub Enrichment**: Search and rerank GitHub repositories
5. **Save Enrichments**: Persist GitHub data to database
6. **Save Entry Links**: Store extracted links for each entry

**Input**:

```python
ContextCollectionInput(entry_ids: list[str])
```

**Output**:

```python
ContextCollectionOutput(
    status: str,              # "completed", "partial", "error"
    total_entries: int,
    successful_extractions: int,
    failed_extractions: int,
    plan: list[str],          # Execution plan/analysis
    enrichment_results: list[dict],
)
```

### FetchEntryLinksWorkflow

User-triggered workflow that fetches web page content for selected links.

**Location**: `worker/buun_curator/workflows/fetch_entry_links.py`

**Trigger**: User clicks "+" button on a link in the Context Panel.

**Steps**:

1. **Receive URLs**: Get list of URLs to fetch from user selection
2. **Fetch Content**: Use `ContentFetcher` to retrieve web page content
3. **Extract Title**: Get page title from HTML metadata or content
4. **Save Enrichment**: Store as `web_page` type in `entry_enrichments` table

**Input**:

```python
FetchEntryLinksInput(
    entry_id: str,
    urls: list[str],
    timeout: int = 60,
)
```

**Output**:

```python
FetchEntryLinksResult(
    status: str,         # "completed", "partial", "failed", "no_urls"
    fetched_count: int,
    failed_count: int,
)
```

## Data Models

### EntryContext

Main context model extracted from entries.

**Location**: `worker/buun_curator/models/context.py`

```python
class EntryContext(BaseModel):
    # Classification
    domain: SubjectDomain       # What the entry is about
    content_type: ContentType   # Format/intent of the entry
    language: str               # ISO 639-1 code (e.g., "en", "ja")
    confidence: float           # Classification confidence (0.0-1.0)

    # Entities and relationships
    entities: list[EntityInfo]
    relationships: list[Relationship]

    # Content analysis
    key_points: list[str]       # Main takeaways (3-5 items)

    # Links extracted from Markdown
    extracted_links: list[ExtractedLink]

    # Metadata
    metadata: EntryMetadata
```

### SubjectDomain

Entry subject domain classification.

| Value | Description |
|-------|-------------|
| `software` | OSS, tools, libraries, frameworks, programming |
| `technology` | Hardware, systems, infrastructure, AI/ML |
| `business` | Companies, startups, organizations, markets |
| `research` | Academic papers, research, science |
| `people` | Individuals, interviews, profiles, careers |
| `industry` | Industry trends, movements, events |
| `product` | Products, gadgets, consumer services |
| `politics` | Politics, policy, regulations |
| `economy` | Economy, finance, markets |
| `society` | Society, culture, lifestyle |
| `health` | Health, medical |
| `environment` | Environment, climate |
| `other` | Doesn't fit predefined categories |

### ContentType

Entry content type/format.

| Value | Description |
|-------|-------------|
| `announcement` | New features, releases, launches |
| `news` | News reporting, current events |
| `tutorial` | How-to guides, educational content |
| `opinion` | Personal opinions, analysis, commentary |
| `comparison` | Comparisons, evaluations, benchmarks |
| `proposal` | RFCs, design proposals |
| `criticism` | Critiques, problem statements |
| `solution` | Solutions, workarounds, fixes |
| `report` | Benchmarks, experiment results, reports |
| `interview` | Interviews |
| `review` | Reviews, evaluations |
| `other` | Doesn't fit predefined categories |

### EntityType

Entity types aligned with the ontology.

**Agents**:

- `Person`, `Organization`, `Company`
- `GovernmentOrganization`, `EducationalOrganization`, `MediaOrganization`
- `Community`

**Places**:

- `Place`, `Country`, `City`

**Creative Works**:

- `CreativeWork`, `Article`, `Book`, `WebSite`, `Software`

**Products & Services**:

- `Product`, `Service`

**Events**:

- `Event`, `BusinessEvent`, `SocialEvent`

**Concepts**:

- `Concept`, `Technology`, `Topic`, `Law`, `FinancialInstrument`, `Disease`

**Language**:

- `Language`

### EntityRole

Role of an entity within the entry.

| Value | Description |
|-------|-------------|
| `author` | Author of the entry |
| `subject` | Main subject of the entry |
| `mentioned` | Mentioned in passing |
| `compared` | Used for comparison |

### RelationType

Relationship types between entities.

**Agent Relations**:

- `createdBy`, `worksFor`, `foundedBy`, `leaderOf`

**Organization Relations**:

- `subsidiaryOf`, `partnersWith`, `competesWith`

**Product/Service Relations**:

- `produces`, `uses`, `basedOn`

**Location Relations**:

- `locatedIn`

**Event Relations**:

- `participatesIn`, `organizedBy`

**Content Relations**:

- `about`, `mentions`, `relatedTo`

**Regulatory Relations**:

- `regulatedBy`, `affects`

**Language Relations**:

- `inLanguage`

### Relationship Direction

Relationships follow a consistent `source → relation → target` pattern:

**Active relations** (source performs action on target):

- `produces`: "Meta produces Pyrefly" → source=Meta, target=Pyrefly
- `uses`: "Pyrefly uses Rust" → source=Pyrefly, target=Rust
- `competesWith`: "Pyrefly competesWith Mypy" → source=Pyrefly, target=Mypy

**Passive relations** (source is acted upon by target):

- `createdBy`: "Pyrefly createdBy Meta" → source=Pyrefly, target=Meta
- `worksFor`: "Person worksFor Company" → source=Person, target=Company
- `basedOn`: "Pyrefly basedOn Rust" → source=Pyrefly, target=Rust

## Enrichment

Enrichments are additional data attached to entries, stored in the `entry_enrichments` table.

### Enrichment Types

| Type | Trigger | Description |
|------|---------|-------------|
| `github` | Automatic | Repository info for software entities |
| `web_page` | User action | Content from linked web pages |

### GitHub Enrichment

Software entities are automatically enriched with GitHub repository data during context collection.

**Process**:

1. **Candidate Collection**: Identify `Software` entities with `subject` or `compared` roles
2. **Skip Well-Known**: Skip common languages/tools (Python, Git, Docker, etc.)
3. **GitHub Search**: Search for matching repositories
4. **LLM Reranking**: Use LLM to select the best match based on entry context
5. **README Fetch**: Retrieve README content for the selected repository

**Database Record**:

```python
{
    "entry_id": "01JXXXXXX",
    "enrichment_type": "github",
    "source": "owner/repo",  # Full repository name
    "data": {
        "name": "entity_name",
        "found": True,
        "repo": {
            "owner": "github_owner",
            "repo": "repo_name",
            "full_name": "owner/repo",
            "description": "Repository description",
            "url": "https://github.com/owner/repo",
            "stars": 1234,
            "forks": 56,
            "language": "Python",
            "topics": ["topic1", "topic2"],
            "license": "MIT",
            "homepage": "https://example.com",
            "readme_filename": "README.md",
            "readme_content": "# Project...",
        },
        "reason": "Selected because...",
    },
}
```

### Web Page Enrichment

Web page content is fetched on-demand when users select links from the Context Panel.

**Process**:

1. **Link Extraction**: During context extraction, links are parsed from markdown content
2. **Link Storage**: Links are saved to `entry_links` table via ContextCollectionWorkflow
3. **User Selection**: User clicks "+" on a link in the Context Panel
4. **Content Fetch**: FetchEntryLinksWorkflow fetches the web page content
5. **Enrichment Save**: Content saved to `entry_enrichments` with type `web_page`

**Database Record**:

```python
{
    "entry_id": "01JXXXXXX",
    "enrichment_type": "web_page",
    "source": "https://example.com/article",  # Original URL
    "data": {
        "title": "Article Title",
        "content": "# Full markdown content...",
        "fetchedAt": "2025-01-15T10:30:00Z",
    },
    "metadata": {
        "contentLength": 12345,
    },
}
```

**Use Cases**:

- Fetch documentation pages referenced in entries
- Retrieve blog posts or articles linked in the content
- Gather additional context for Deep Research

## Related Files

**Workflows**:

- `worker/buun_curator/workflows/extract_entry_context.py` - Entry context extraction
- `worker/buun_curator/workflows/context_collection.py` - Multi-entry orchestration
- `worker/buun_curator/workflows/fetch_entry_links.py` - Web page enrichment

**Activities**:

- `worker/buun_curator/activities/context/extract_context.py` - LLM extraction
- `worker/buun_curator/activities/fetch.py` - Content fetching (includes `fetch_and_save_entry_links`)

**Models**:

- `worker/buun_curator/models/context.py` - Context data models
- `worker/buun_curator/models/activity_io.py` - Workflow/activity I/O models
