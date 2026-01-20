"""
Generate multi-hop evaluation dataset for Research Agent.

Creates QA pairs that require information from multiple entries,
testing the agent's ability to retrieve and synthesize across documents.

Workflow
--------
1. cluster: Group entries by embedding similarity using K-means
2. generate: Create multi-hop questions from entry clusters
3. filter: Remove questions solvable from single entries (shortcuts)

Required Environment Variables
------------------------------
DATABASE_URL : str
    PostgreSQL connection URL for fetching entries.
OPENAI_API_KEY : str
    API key for OpenAI-compatible LLM service (for generate/filter).

Optional Environment Variables
------------------------------
OPENAI_BASE_URL : str
    Base URL for OpenAI-compatible LLM service.
LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST : str
    Langfuse credentials for dataset upload.

Output Directory Structure
--------------------------
evaluation/<dataset-name>/
├── data/
│   ├── clusters.json        # Entry clusters from Step 1
│   └── multihop_qa.json     # Generated QA pairs from Step 2-3
└── results/                 # Evaluation results

Usage
-----
cd worker

# Step 1: Cluster entries
uv run generate-multihop-dataset cluster --n-clusters 20

# Step 2: Generate multi-hop questions
uv run generate-multihop-dataset generate --questions-per-cluster 2

# Step 3: Filter out shortcut-solvable questions
uv run generate-multihop-dataset filter

# Or run all steps
uv run generate-multihop-dataset all
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

import click
import numpy as np
import psycopg
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import Langfuse
from pydantic import BaseModel, Field
from sklearn.cluster import KMeans

# Japanese feed patterns for language detection
JA_FEED_PATTERNS = [
    r"zenn\.dev",
    r"gigazine\.net",
    r"gihyo\.jp",
    r"classmethod\.jp",
    r"postd\.cc",
    r"publickey1\.jp",
    r"automaton-media\.com",
    r"qiita\.com",
]


def detect_language(feed_url: str, title: str) -> str:
    """
    Detect language from feed URL and title.

    Parameters
    ----------
    feed_url : str
        Feed URL.
    title : str
        Entry title.

    Returns
    -------
    str
        'ja' or 'en'.
    """
    for pattern in JA_FEED_PATTERNS:
        if re.search(pattern, feed_url, re.IGNORECASE):
            return "ja"

    if re.search(r"[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]", title):
        return "ja"

    return "en"


def get_db_connection():
    """
    Get database connection from DATABASE_URL.

    Returns
    -------
    psycopg.Connection
        Database connection.

    Raises
    ------
    click.ClickException
        If DATABASE_URL is not set.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise click.ClickException("DATABASE_URL environment variable not set")
    return psycopg.connect(database_url)


def fetch_entries_with_embeddings(
    conn,
    min_content_length: int = 500,
) -> list[dict]:
    """
    Fetch entries with embeddings and keep=true.

    Parameters
    ----------
    conn : psycopg.Connection
        Database connection.
    min_content_length : int
        Minimum content length filter.

    Returns
    -------
    list[dict]
        List of entry dictionaries with embeddings.
    """
    query = """
    SELECT
        e.id,
        e.title,
        e.url,
        e.embedding::text as embedding,
        COALESCE(e.filtered_content, e.full_content) as content,
        f.url as feed_url,
        f.name as feed_name,
        c.name as category_name
    FROM entries e
    JOIN feeds f ON e.feed_id = f.id
    LEFT JOIN categories c ON f.category_id = c.id
    WHERE e.keep = true
      AND e.embedding IS NOT NULL
      AND (
        LENGTH(COALESCE(e.filtered_content, '')) > %s
        OR LENGTH(COALESCE(e.full_content, '')) > %s
      )
    ORDER BY e.published_at DESC
    """

    with conn.cursor() as cur:
        cur.execute(query, (min_content_length, min_content_length))
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    entries = []
    for row in rows:
        entry = dict(zip(columns, row, strict=True))

        # Parse embedding from PostgreSQL array format
        embedding_str = entry["embedding"]
        if embedding_str:
            embedding_str = embedding_str.strip("[]")
            entry["embedding"] = np.array([float(x) for x in embedding_str.split(",")])

        entry["language"] = detect_language(entry["feed_url"], entry["title"])
        entries.append(entry)

    return entries


def cluster_entries(
    entries: list[dict],
    n_clusters: int,
    min_cluster_size: int = 2,
) -> list[dict]:
    """
    Cluster entries using K-means on embeddings.

    Parameters
    ----------
    entries : list[dict]
        List of entries with embeddings.
    n_clusters : int
        Number of clusters to create.
    min_cluster_size : int
        Minimum entries per cluster to keep.

    Returns
    -------
    list[dict]
        List of cluster dictionaries.
    """
    if len(entries) < n_clusters:
        n_clusters = max(1, len(entries) // min_cluster_size)
        click.echo(f"  Adjusted n_clusters to {n_clusters} (limited by entry count)")

    embeddings = np.array([e["embedding"] for e in entries])

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)  # type: ignore[arg-type]
    kmeans.fit(embeddings)

    # Group entries by cluster
    labels = kmeans.labels_
    if labels is None:
        return []

    cluster_map: dict[int, list[dict]] = {}
    for i, entry in enumerate(entries):
        label = int(labels[i])
        if label not in cluster_map:
            cluster_map[label] = []
        cluster_map[label].append(entry)

    # Build cluster objects
    clusters = []
    for cluster_id, cluster_entries in sorted(cluster_map.items()):
        if len(cluster_entries) < min_cluster_size:
            continue

        # Find centroid entry (closest to cluster center)
        center = kmeans.cluster_centers_[cluster_id]
        cluster_embeddings = np.array([e["embedding"] for e in cluster_entries])
        distances = np.linalg.norm(cluster_embeddings - center, axis=1)
        centroid_idx = int(np.argmin(distances))
        centroid_entry = cluster_entries[centroid_idx]

        # Collect titles for topic summary hint
        titles = [e["title"] for e in cluster_entries[:5]]

        clusters.append(
            {
                "cluster_id": cluster_id,
                "centroid_entry_id": centroid_entry["id"],
                "centroid_title": centroid_entry["title"],
                "entry_count": len(cluster_entries),
                "entries": [
                    {
                        "entry_id": e["id"],
                        "title": e["title"],
                        "url": e["url"],
                        "language": e["language"],
                        "feed_name": e["feed_name"],
                        "category": e["category_name"],
                    }
                    for e in cluster_entries
                ],
                "sample_titles": titles,
            }
        )

    return clusters


# --- Pydantic models for structured output ---


class GeneratedQuestion(BaseModel):
    """A multi-hop question generated from multiple entries."""

    question: str = Field(description="The multi-hop question in the same language as the entries")
    question_type: str = Field(
        description="Type of question: 'comparison', 'synthesis', or 'analysis'"
    )
    reasoning: str = Field(description="Why this question requires multiple entries to answer")


class GeneratedQuestions(BaseModel):
    """List of generated multi-hop questions."""

    questions: list[GeneratedQuestion] = Field(description="List of generated questions")


class ShortcutCheckResult(BaseModel):
    """Result of checking if a question can be answered from a single entry."""

    can_answer: bool = Field(
        description="True if the question can be fully answered from this single entry"
    )
    confidence: str = Field(description="Confidence level: 'high', 'medium', or 'low'")
    explanation: str = Field(description="Brief explanation of the assessment")


# --- LLM-based question generation ---


QUESTION_GENERATION_PROMPT = """You are an expert in creating evaluation datasets for RAG systems.
Read the following entries and generate questions that require retrieving and \
synthesizing information from multiple sources.

## Reference Entries

{entries_text}

## Instructions

Generate {n_questions} questions of the following types:

1. **Comparison**: Ask about differences between two or more concepts, \
technologies, or approaches
2. **Synthesis**: Require combining information from multiple sources
3. **Analysis**: Analyze commonalities, differences, or patterns

## Critical Requirements

### Self-Contained Questions
- **NO numbered references**: Do NOT reference "Entry 1", "Entry 2", etc.
- Mention specific topics, technologies, or concepts BY NAME \
so the agent can search for them.

### Natural Connections Only
- **SKIP if unrelated**: If entries cover completely unrelated topics \
with no natural connection, generate FEWER questions or return empty.
- Prefer NATURAL connections: same technology domain, related concepts, \
similar problems, or shared context.
- Do NOT force artificial connections between unrelated topics.

### Keep Questions Concise
- Maximum 150 characters for English, 80 characters for Japanese.
- Focus on ONE clear comparison or synthesis per question.
- Avoid compound questions with multiple sub-questions.

### Language Matching
- Generate questions in the SAME LANGUAGE as the entries.

## Quality Checklist (before generating each question)

1. Would a researcher naturally ask this question?
2. Are the entries genuinely related on this topic?
3. Can the answer be found by searching for the named concepts?

If any answer is "no", skip that question.

## Examples

GOOD: "How does LangChain's tool calling compare to LangGraph's orchestration?"
GOOD: "LangChainとLangGraphのエージェント設計の違いは？"

BAD (too long): "How does the approach mentioned in the first entry regarding \
distributed systems compare to the methodology described in the second entry \
about microservices architecture in terms of scalability and fault tolerance?"

BAD (forced connection): "How does CSS styling relate to quantum computing?"

BAD (numbered reference): "What does Entry 1 describe?"
"""


def get_llm(model: str) -> ChatOpenAI:
    """
    Get LLM instance with configured settings.

    Parameters
    ----------
    model : str
        Model name to use.

    Returns
    -------
    ChatOpenAI
        Configured LLM instance.
    """
    return ChatOpenAI(
        model=model,
        temperature=0.7,
        base_url=os.environ.get("OPENAI_BASE_URL"),
    )


def fetch_entry_contents(conn, entry_ids: list[str]) -> dict[str, dict]:
    """
    Fetch entry contents from database.

    Parameters
    ----------
    conn : psycopg.Connection
        Database connection.
    entry_ids : list[str]
        List of entry IDs to fetch.

    Returns
    -------
    dict[str, dict]
        Mapping of entry_id to entry data with content.
    """
    if not entry_ids:
        return {}

    placeholders = ",".join(["%s"] * len(entry_ids))
    query = f"""
    SELECT
        id,
        title,
        url,
        COALESCE(filtered_content, full_content) as content
    FROM entries
    WHERE id IN ({placeholders})
    """

    with conn.cursor() as cur:
        cur.execute(query, entry_ids)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return {row[0]: dict(zip(columns, row, strict=True)) for row in rows}


def fetch_entry_embeddings(conn, entry_ids: list[str]) -> dict[str, np.ndarray]:
    """
    Fetch entry embeddings from database.

    Parameters
    ----------
    conn : psycopg.Connection
        Database connection.
    entry_ids : list[str]
        List of entry IDs to fetch.

    Returns
    -------
    dict[str, np.ndarray]
        Mapping of entry_id to embedding array.
    """
    if not entry_ids:
        return {}

    placeholders = ",".join(["%s"] * len(entry_ids))
    query = f"""
    SELECT id, embedding::text as embedding
    FROM entries
    WHERE id IN ({placeholders}) AND embedding IS NOT NULL
    """

    with conn.cursor() as cur:
        cur.execute(query, entry_ids)
        rows = cur.fetchall()

    embeddings = {}
    for row in rows:
        entry_id = row[0]
        embedding_str = row[1]
        if embedding_str:
            embedding_str = embedding_str.strip("[]")
            embeddings[entry_id] = np.array([float(x) for x in embedding_str.split(",")])

    return embeddings


def compute_pairwise_similarities(embeddings: np.ndarray) -> np.ndarray:
    """
    Compute pairwise cosine similarities between embeddings.

    Parameters
    ----------
    embeddings : np.ndarray
        Array of embeddings with shape (n_samples, n_features).

    Returns
    -------
    np.ndarray
        Pairwise similarity matrix with shape (n_samples, n_samples).
    """
    # Normalize embeddings
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms
    # Compute cosine similarity matrix
    return np.dot(normalized, normalized.T)


def select_similar_entries(
    entries: list[dict],
    embeddings: dict[str, np.ndarray],
    n_select: int = 2,
    min_similarity: float = 0.5,
) -> list[dict]:
    """
    Select entries with high pairwise similarity.

    Parameters
    ----------
    entries : list[dict]
        List of entry dicts with entry_id.
    embeddings : dict[str, np.ndarray]
        Mapping of entry_id to embedding.
    n_select : int
        Number of entries to select.
    min_similarity : float
        Minimum pairwise similarity threshold.

    Returns
    -------
    list[dict]
        Selected entries with high similarity (guaranteed unique entry_ids).
    """
    # Deduplicate entries by entry_id and title
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    unique_entries = []
    for entry in entries:
        entry_id = entry.get("entry_id") or entry.get("id")
        title = entry.get("title", "")
        # Skip if we've seen this ID or this exact title
        if entry_id and entry_id not in seen_ids and title not in seen_titles:
            seen_ids.add(entry_id)
            if title:
                seen_titles.add(title)
            unique_entries.append(entry)

    if len(unique_entries) <= n_select:
        return unique_entries

    # Get embeddings for entries
    entry_embeddings = []
    valid_entries = []
    for entry in unique_entries:
        entry_id = entry.get("entry_id") or entry.get("id")
        if entry_id and entry_id in embeddings:
            entry_embeddings.append(embeddings[entry_id])
            valid_entries.append(entry)

    if len(valid_entries) < n_select:
        return valid_entries

    emb_array = np.array(entry_embeddings)
    sim_matrix = compute_pairwise_similarities(emb_array)

    # Find the best pair (highest similarity, excluding self)
    np.fill_diagonal(sim_matrix, -1)  # Exclude self-similarity
    best_pair = np.unravel_index(np.argmax(sim_matrix), sim_matrix.shape)
    best_similarity = sim_matrix[best_pair]

    if best_similarity < min_similarity:
        # No pair meets threshold, return first two by default
        return valid_entries[:n_select]

    return [valid_entries[best_pair[0]], valid_entries[best_pair[1]]]


def truncate_content(content: str, max_chars: int = 3000) -> str:
    """
    Truncate content to max characters.

    Parameters
    ----------
    content : str
        Content to truncate.
    max_chars : int
        Maximum characters to keep.

    Returns
    -------
    str
        Truncated content.
    """
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n[... truncated ...]"


def generate_questions_for_cluster(
    llm: ChatOpenAI,
    entries: list[dict],
    n_questions: int,
) -> list[dict]:
    """
    Generate multi-hop questions for a cluster of entries.

    Parameters
    ----------
    llm : ChatOpenAI
        LLM instance.
    entries : list[dict]
        List of entry dicts with content.
    n_questions : int
        Number of questions to generate.

    Returns
    -------
    list[dict]
        Generated questions with metadata.
    """
    # Format entries for prompt (use titles only, no "Article X" numbering)
    entries_text = ""
    for entry in entries:
        content = truncate_content(entry.get("content", ""))
        entries_text += f"### {entry['title']}\n\n{content}\n\n"

    prompt = ChatPromptTemplate.from_template(QUESTION_GENERATION_PROMPT)
    structured_llm = llm.with_structured_output(GeneratedQuestions)

    try:
        result: GeneratedQuestions | None = structured_llm.invoke(  # type: ignore[assignment]
            prompt.format(entries_text=entries_text, n_questions=n_questions)
        )
        if result is None:
            return []

        questions = []
        for q in result.questions:
            questions.append(
                {
                    "question": q.question,
                    "question_type": q.question_type,
                    "reasoning": q.reasoning,
                    "source_entry_ids": [e["id"] for e in entries],
                    "source_titles": [e["title"] for e in entries],
                }
            )
        return questions

    except Exception as e:
        click.echo(f"    Error generating questions: {e}")
        return []


SHORTCUT_CHECK_PROMPT = """You are a quality checker for evaluation datasets.
Determine whether the following question can be fully answered using only \
the single entry provided.

## Question
{question}

## Entry
### {title}

{content}

## Instructions
Can this single entry alone fully answer the question above?
If only a partial answer is possible, respond with "cannot answer".
Only respond with "can answer" if ALL information needed for a complete answer \
is contained in this entry.
"""


def check_shortcut_solvable(
    llm: ChatOpenAI,
    question: str,
    entry: dict,
) -> bool:
    """
    Check if a question can be answered from a single entry.

    Parameters
    ----------
    llm : ChatOpenAI
        LLM instance.
    question : str
        The question to check.
    entry : dict
        Entry with content.

    Returns
    -------
    bool
        True if the question can be fully answered from this single entry.
    """
    content = truncate_content(entry.get("content", ""), max_chars=4000)
    prompt = ChatPromptTemplate.from_template(SHORTCUT_CHECK_PROMPT)
    structured_llm = llm.with_structured_output(ShortcutCheckResult)

    try:
        result: ShortcutCheckResult | None = structured_llm.invoke(  # type: ignore[assignment]
            prompt.format(
                question=question,
                title=entry["title"],
                content=content,
            )
        )
        if result is None:
            return False
        return result.can_answer and result.confidence == "high"

    except Exception as e:
        click.echo(f"    Error checking shortcut: {e}")
        return False


class OrderedGroup(click.Group):
    """Click group that maintains command order."""

    def list_commands(self, ctx: click.Context) -> list[str]:  # noqa: ARG002
        """Return commands in definition order."""
        return list(self.commands.keys())


@click.group(cls=OrderedGroup)
@click.option(
    "--dataset-name",
    default="multihop-evaluation",
    help="Dataset name for directory (default: multihop-evaluation)",
)
@click.pass_context
def cli(ctx, dataset_name: str):
    """Generate multi-hop evaluation dataset for Research Agent."""
    ctx.ensure_object(dict)
    ctx.obj["dataset_name"] = dataset_name
    ctx.obj["output_dir"] = Path("evaluation") / dataset_name / "data"


@cli.command("cluster")
@click.option(
    "--n-clusters",
    default=20,
    type=int,
    help="Number of clusters to create (default: 20)",
)
@click.option(
    "--min-cluster-size",
    default=2,
    type=int,
    help="Minimum entries per cluster (default: 2)",
)
@click.option(
    "--min-content-length",
    default=500,
    type=int,
    help="Minimum content length for entries (default: 500)",
)
@click.pass_context
def cluster_cmd(
    ctx,
    n_clusters: int,
    min_cluster_size: int,
    min_content_length: int,
):
    """Step 1: Cluster entries by embedding similarity."""
    output_dir: Path = ctx.obj["output_dir"]

    click.echo("=" * 60)
    click.echo("Step 1: Clustering entries by embedding similarity")
    click.echo("=" * 60)

    # Fetch entries
    click.echo(f"\nFetching entries with embeddings (min length: {min_content_length})...")
    conn = get_db_connection()
    try:
        entries = fetch_entries_with_embeddings(conn, min_content_length)
    finally:
        conn.close()

    click.echo(f"  Found {len(entries)} entries")

    en_count = sum(1 for e in entries if e["language"] == "en")
    ja_count = sum(1 for e in entries if e["language"] == "ja")
    click.echo(f"  English: {en_count}, Japanese: {ja_count}")

    # Cluster entries
    click.echo(f"\nClustering into {n_clusters} clusters...")
    clusters = cluster_entries(entries, n_clusters, min_cluster_size)
    click.echo(f"  Created {len(clusters)} clusters (min size: {min_cluster_size})")

    # Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "clusters.json"

    output = {
        "created_at": datetime.now().isoformat(),
        "metadata": {
            "n_clusters_requested": n_clusters,
            "n_clusters_created": len(clusters),
            "min_cluster_size": min_cluster_size,
            "min_content_length": min_content_length,
            "total_entries": len(entries),
            "algorithm": "kmeans",
        },
        "clusters": clusters,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    click.echo(f"\nSaved clusters to {output_path}")

    # Print summary
    click.echo("\nCluster Summary:")
    for cluster in clusters[:10]:
        click.echo(
            f"  Cluster {cluster['cluster_id']}: "
            f"{cluster['entry_count']} entries, "
            f"centroid: {cluster['centroid_title'][:50]}..."
        )
    if len(clusters) > 10:
        click.echo(f"  ... and {len(clusters) - 10} more clusters")


@cli.command("generate")
@click.option(
    "--questions-per-cluster",
    default=2,
    type=int,
    help="Number of questions per cluster (default: 2)",
)
@click.option(
    "--max-clusters",
    default=None,
    type=int,
    help="Maximum clusters to process (default: all)",
)
@click.option(
    "--min-similarity",
    default=0.5,
    type=float,
    help="Minimum cosine similarity between selected entries (default: 0.5)",
)
@click.option(
    "--llm-model",
    default=None,
    help="LLM model for generation (default: $EVAL_DATA_LLM_MODEL or gpt-4o-mini)",
)
@click.pass_context
def generate_cmd(
    ctx,
    questions_per_cluster: int,
    max_clusters: int | None,
    min_similarity: float,
    llm_model: str | None,
):
    """Step 2: Generate multi-hop questions from clusters."""
    output_dir: Path = ctx.obj["output_dir"]
    clusters_path = output_dir / "clusters.json"

    if not clusters_path.exists():
        raise click.ClickException(f"{clusters_path} not found. Run 'cluster' command first.")

    click.echo("=" * 60)
    click.echo("Step 2: Generating multi-hop questions")
    click.echo("=" * 60)

    # Load clusters
    with open(clusters_path, encoding="utf-8") as f:
        clusters_data = json.load(f)

    clusters = clusters_data["clusters"]
    if max_clusters:
        clusters = clusters[:max_clusters]

    model = llm_model or os.environ.get("EVAL_DATA_LLM_MODEL", "gpt-4o-mini")
    click.echo(f"\nProcessing {len(clusters)} clusters...")
    click.echo(f"  Questions per cluster: {questions_per_cluster}")
    click.echo(f"  Min similarity: {min_similarity}")
    click.echo(f"  LLM model: {model}")

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        raise click.ClickException("OPENAI_API_KEY environment variable not set")

    # Initialize LLM
    llm = get_llm(model)

    # Fetch all entry contents and embeddings
    click.echo("\nFetching entry contents and embeddings from database...")
    all_entry_ids = []
    for cluster in clusters:
        all_entry_ids.extend([e["entry_id"] for e in cluster["entries"]])

    conn = get_db_connection()
    try:
        entry_contents = fetch_entry_contents(conn, all_entry_ids)
        # Fetch embeddings for similarity calculation
        entry_embeddings = fetch_entry_embeddings(conn, all_entry_ids)
    finally:
        conn.close()
    click.echo(f"  Fetched {len(entry_contents)} entries with embeddings")

    # Generate questions for each cluster
    all_questions: list[dict] = []
    for i, cluster in enumerate(clusters):
        click.echo(
            f"\n[{i + 1}/{len(clusters)}] Cluster {cluster['cluster_id']}: "
            f"{cluster['entry_count']} entries"
        )

        # Select 2 most similar entries from the cluster
        cluster_entries = cluster["entries"]
        selected = select_similar_entries(
            cluster_entries, entry_embeddings, n_select=2, min_similarity=min_similarity
        )

        # Get content for selected entries
        entries_with_content = []
        for entry in selected:
            entry_id = entry["entry_id"]
            if entry_id in entry_contents:
                entry_data = entry_contents[entry_id]
                entries_with_content.append(
                    {
                        "id": entry_id,
                        "title": entry_data["title"],
                        "url": entry_data["url"],
                        "content": entry_data["content"],
                    }
                )

        if len(entries_with_content) < 2:
            click.echo("    Skipping: not enough entries with content")
            continue

        click.echo(f"    Selected {len(entries_with_content)} entries:")
        for e in entries_with_content:
            click.echo(f"      - {e['title'][:60]}...")

        # Generate questions
        questions = generate_questions_for_cluster(llm, entries_with_content, questions_per_cluster)
        click.echo(f"    Generated {len(questions)} questions")

        for q in questions:
            q["cluster_id"] = cluster["cluster_id"]
            all_questions.append(q)

    # Save results
    output_path = output_dir / "multihop_qa.json"
    output = {
        "created_at": datetime.now().isoformat(),
        "metadata": {
            "questions_per_cluster": questions_per_cluster,
            "clusters_processed": len(clusters),
            "llm_model": model,
            "total_questions": len(all_questions),
            "status": "generated",
        },
        "qa_samples": all_questions,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    click.echo(f"\nSaved {len(all_questions)} questions to {output_path}")

    # Print sample questions
    if all_questions:
        click.echo("\nSample questions:")
        for q in all_questions[:3]:
            click.echo(f"  [{q['question_type']}] {q['question'][:80]}...")


@cli.command("filter")
@click.option(
    "--llm-model",
    default=None,
    help="LLM model for shortcut detection (default: $EVAL_DATA_LLM_MODEL or gpt-4o-mini)",
)
@click.pass_context
def filter_cmd(ctx, llm_model: str | None):
    """Step 3: Filter out shortcut-solvable questions."""
    output_dir: Path = ctx.obj["output_dir"]
    qa_path = output_dir / "multihop_qa.json"

    if not qa_path.exists():
        raise click.ClickException(f"{qa_path} not found. Run 'generate' command first.")

    click.echo("=" * 60)
    click.echo("Step 3: Filtering shortcut-solvable questions")
    click.echo("=" * 60)

    # Load QA samples
    with open(qa_path, encoding="utf-8") as f:
        qa_data = json.load(f)

    samples = qa_data.get("qa_samples", [])
    click.echo(f"\nLoaded {len(samples)} QA samples")

    if not samples:
        click.echo("No samples to filter")
        return

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        raise click.ClickException("OPENAI_API_KEY environment variable not set")

    model = llm_model or os.environ.get("EVAL_DATA_LLM_MODEL", "gpt-4o-mini")
    click.echo(f"  LLM model: {model}")

    # Initialize LLM
    llm = get_llm(model)

    # Fetch entry contents for shortcut checking
    click.echo("\nFetching entry contents from database...")
    all_entry_ids = []
    for sample in samples:
        all_entry_ids.extend(sample.get("source_entry_ids", []))
    all_entry_ids = list(set(all_entry_ids))

    conn = get_db_connection()
    try:
        entry_contents = fetch_entry_contents(conn, all_entry_ids)
    finally:
        conn.close()
    click.echo(f"  Fetched {len(entry_contents)} entries")

    # Check each question for shortcuts
    click.echo("\nChecking for shortcut-solvable questions...")
    filtered_samples = []
    shortcut_count = 0

    for i, sample in enumerate(samples):
        question = sample["question"]
        entry_ids = sample.get("source_entry_ids", [])

        click.echo(f"\n[{i + 1}/{len(samples)}] {question[:60]}...")

        # Check if any single entry can answer the question
        is_shortcut = False
        for entry_id in entry_ids:
            if entry_id not in entry_contents:
                continue

            entry = entry_contents[entry_id]
            if check_shortcut_solvable(llm, question, entry):
                click.echo(f"    ⚠ Shortcut detected: answerable from '{entry['title'][:40]}...'")
                is_shortcut = True
                break

        if is_shortcut:
            shortcut_count += 1
            sample["filtered_reason"] = "shortcut_solvable"
        else:
            click.echo("    ✓ Multi-hop required")
            filtered_samples.append(sample)

    # Update and save results
    qa_data["qa_samples"] = filtered_samples
    qa_data["metadata"]["status"] = "filtered"
    qa_data["metadata"]["filtered_at"] = datetime.now().isoformat()
    qa_data["metadata"]["shortcut_removed"] = shortcut_count
    qa_data["metadata"]["final_count"] = len(filtered_samples)

    with open(qa_path, "w", encoding="utf-8") as f:
        json.dump(qa_data, f, ensure_ascii=False, indent=2)

    click.echo(f"\n{'=' * 60}")
    click.echo("Filtering Summary")
    click.echo("=" * 60)
    click.echo(f"  Original questions: {len(samples)}")
    click.echo(f"  Shortcut-solvable (removed): {shortcut_count}")
    click.echo(f"  Final questions: {len(filtered_samples)}")
    click.echo(f"\nSaved to {qa_path}")


@cli.command("all")
@click.pass_context
def all_cmd(ctx):
    """Run all steps: cluster → generate → filter."""
    ctx.invoke(cluster_cmd)
    ctx.invoke(generate_cmd)
    ctx.invoke(filter_cmd)


def get_langfuse_client() -> Langfuse:
    """
    Get Langfuse client from environment variables.

    Returns
    -------
    Langfuse
        Langfuse client instance.

    Raises
    ------
    click.ClickException
        If required environment variables are not set.
    """
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")

    if not public_key or not secret_key:
        raise click.ClickException(
            "LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables required"
        )

    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=os.environ.get("LANGFUSE_HOST"),
    )


@cli.command("upload")
@click.option(
    "--langfuse-dataset-name",
    default=None,
    help="Langfuse dataset name (default: same as --dataset-name)",
)
@click.pass_context
def upload_cmd(ctx, langfuse_dataset_name: str | None):
    """Step 4: Upload filtered questions to Langfuse Dataset."""
    output_dir: Path = ctx.obj["output_dir"]
    dataset_name: str = ctx.obj["dataset_name"]
    qa_path = output_dir / "multihop_qa.json"

    if not qa_path.exists():
        raise click.ClickException(f"{qa_path} not found. Run 'filter' command first.")

    click.echo("=" * 60)
    click.echo("Step 4: Uploading to Langfuse Dataset")
    click.echo("=" * 60)

    # Load QA samples
    with open(qa_path, encoding="utf-8") as f:
        qa_data = json.load(f)

    samples = qa_data.get("qa_samples", [])
    metadata = qa_data.get("metadata", {})

    if not samples:
        click.echo("No samples to upload")
        return

    if metadata.get("status") != "filtered":
        click.echo(
            "Warning: QA data has not been filtered. Run 'filter' command first for best results."
        )

    # Initialize Langfuse client
    langfuse = get_langfuse_client()

    # Determine dataset name
    target_dataset_name = langfuse_dataset_name or dataset_name
    click.echo(f"\nUploading {len(samples)} samples to dataset: {target_dataset_name}")

    # Create or get dataset
    try:
        langfuse.get_dataset(target_dataset_name)
        click.echo(f"  Found existing dataset: {target_dataset_name}")
    except Exception:
        langfuse.create_dataset(
            name=target_dataset_name,
            description="Multi-hop evaluation dataset for Research Agent",
            metadata={
                "created_by": "generate-multihop-dataset",
                "created_at": datetime.now().isoformat(),
            },
        )
        click.echo(f"  Created new dataset: {target_dataset_name}")

    # Upload each sample as a dataset item
    uploaded_count = 0
    for i, sample in enumerate(samples):
        question = sample.get("question", "")
        if not question:
            continue

        # Prepare input and metadata for batch-eval compatibility
        item_input = {"question": question}
        item_metadata = {
            "question_type": sample.get("question_type"),
            "reasoning": sample.get("reasoning"),
            "source_entry_ids": sample.get("source_entry_ids", []),
            "source_titles": sample.get("source_titles", []),
            "cluster_id": sample.get("cluster_id"),
        }

        try:
            langfuse.create_dataset_item(
                dataset_name=target_dataset_name,
                input=item_input,
                metadata=item_metadata,
            )
            uploaded_count += 1
            if (i + 1) % 10 == 0:
                click.echo(f"  Uploaded {i + 1}/{len(samples)} samples...")
        except Exception as e:
            click.echo(f"  Error uploading sample {i + 1}: {e}")

    # Flush to ensure all data is sent
    langfuse.flush()

    click.echo(f"\n{'=' * 60}")
    click.echo("Upload Summary")
    click.echo("=" * 60)
    click.echo(f"  Dataset: {target_dataset_name}")
    click.echo(f"  Total samples: {len(samples)}")
    click.echo(f"  Uploaded: {uploaded_count}")
    click.echo(f"  Failed: {len(samples) - uploaded_count}")


if __name__ == "__main__":
    cli()
