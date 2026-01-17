"""
Generate single-hop evaluation dataset using RAGAS TestsetGenerator.

Samples diverse entries from DB using embedding-based clustering,
then generates QA pairs with RAGAS.

Generates 4 patterns:
- en_en: English Entry -> English Question
- en_ja: English Entry -> Japanese Question
- ja_en: Japanese Entry -> English Question
- ja_ja: Japanese Entry -> Japanese Question

Required Environment Variables
------------------------------
OPENAI_API_KEY : str
    API key for OpenAI-compatible LLM service.
DATABASE_URL : str
    PostgreSQL connection URL for fetching entries.

Optional Environment Variables
------------------------------
OPENAI_BASE_URL : str
    Base URL for OpenAI-compatible LLM service (e.g., LiteLLM proxy).
EVAL_DATA_LLM_MODEL : str
    LLM model for QA generation (default: gpt-4o-mini).
EVAL_DATA_EMBEDDING_LLM_MODEL : str
    HuggingFace embedding model
    (default: sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2).
LANGFUSE_PUBLIC_KEY : str
    Langfuse public key for dataset upload (required for upload command).
LANGFUSE_SECRET_KEY : str
    Langfuse secret key for dataset upload (required for upload command).
LANGFUSE_HOST : str
    Langfuse host URL (default: https://cloud.langfuse.com).

Output Directory Structure
--------------------------
evaluation/<dataset-name>/
+-- data/
|   +-- eval_targets.json    # Sampled entries
|   +-- qa/
|       +-- eval_qa.json     # Generated QA pairs
+-- results/                 # Evaluation results (created by batch-eval)

Usage
-----
cd worker

# Step 1: Sample entries from database
uv run generate-singlehop-eval-dataset sample --n-samples 15

# Step 2: Generate QA pairs with RAGAS
uv run generate-singlehop-eval-dataset generate --dataset-size 10

# Step 3: Upload to Langfuse Dataset
uv run generate-singlehop-eval-dataset upload

# Or run all steps
uv run generate-singlehop-eval-dataset all
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path

import click
import numpy as np
import psycopg
from langchain_core.documents import Document
from langfuse import Langfuse
from openai import OpenAI
from ragas.embeddings import HuggingFaceEmbeddings
from ragas.llms import llm_factory
from ragas.testset import TestsetGenerator
from ragas.testset.graph import NodeType
from ragas.testset.synthesizers.single_hop.specific import (
    SingleHopSpecificQuerySynthesizer,
)
from ragas.testset.transforms import (
    CosineSimilarityBuilder,
    EmbeddingExtractor,
    OverlapScoreBuilder,
    Parallel,
    SummaryExtractor,
)
from ragas.testset.transforms.extractors import NERExtractor
from ragas.testset.transforms.extractors.llm_based import ThemesExtractor
from ragas.testset.transforms.filters import CustomNodeFilter
from ragas.utils import num_tokens_from_string
from sklearn.cluster import KMeans

# Language names for RAGAS adapt_prompts
LANGUAGE_NAMES = {
    "en": "english",
    "ja": "japanese",
}

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


class OrderedGroup(click.Group):
    """Click group that maintains command definition order."""

    def list_commands(self, ctx):  # noqa: ARG002
        return list(self.commands.keys())


def get_database_connection():
    """
    Get database connection from DATABASE_URL environment variable.

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


def fetch_entries_with_embeddings(conn, min_content_length: int = 1000) -> list[dict]:
    """
    Fetch entries with embeddings and keep=true.

    Only includes entries that have filtered_content or full_content
    (excludes entries with only feed_content).

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

        embedding_str = entry["embedding"]
        if embedding_str:
            embedding_str = embedding_str.strip("[]")
            entry["embedding"] = np.array([float(x) for x in embedding_str.split(",")])

        entry["language"] = detect_language(entry["feed_url"], entry["title"])
        entries.append(entry)

    return entries


def sample_diverse_entries(
    entries: list[dict],
    n_samples: int,
    language: str | None = None,
) -> list[dict]:
    """
    Sample diverse entries using K-means clustering.

    Parameters
    ----------
    entries : list[dict]
        List of entries with embeddings.
    n_samples : int
        Number of samples to select.
    language : str | None
        Filter by language ('ja', 'en', or None for all).

    Returns
    -------
    list[dict]
        Sampled entries.
    """
    if language:
        entries = [e for e in entries if e["language"] == language]

    if len(entries) <= n_samples:
        return entries

    embeddings = np.array([e["embedding"] for e in entries])

    kmeans = KMeans(n_clusters=n_samples, random_state=42, n_init=10)  # type: ignore[arg-type]
    kmeans.fit(embeddings)

    selected_indices = []
    for i in range(n_samples):
        cluster_mask = kmeans.labels_ == i
        cluster_indices = np.where(cluster_mask)[0]

        if len(cluster_indices) == 0:
            continue

        cluster_embeddings = embeddings[cluster_indices]
        center = kmeans.cluster_centers_[i]
        distances = np.linalg.norm(cluster_embeddings - center, axis=1)
        closest_idx = cluster_indices[np.argmin(distances)]
        selected_indices.append(closest_idx)

    return [entries[i] for i in selected_indices]


def fetch_entry_content(conn, entry_ids: list[str]) -> dict[str, dict]:
    """
    Fetch entry content from database.

    Parameters
    ----------
    conn : psycopg.Connection
        Database connection.
    entry_ids : list[str]
        List of entry IDs to fetch.

    Returns
    -------
    dict[str, dict]
        Mapping of entry_id to entry data.
    """
    if not entry_ids:
        return {}

    placeholders = ",".join(["%s"] * len(entry_ids))
    query = f"""
    SELECT
        id,
        title,
        url,
        full_content,
        filtered_content,
        summary
    FROM entries
    WHERE id IN ({placeholders})
    """

    with conn.cursor() as cur:
        cur.execute(query, entry_ids)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    return {row[0]: dict(zip(columns, row, strict=True)) for row in rows}


def create_documents(targets: list[dict], entry_contents: dict[str, dict]) -> list[Document]:
    """
    Create LangChain Documents from targets and content.

    Formats content as Markdown with title heading for RAGAS compatibility.

    Parameters
    ----------
    targets : list[dict]
        List of evaluation targets with entry_id.
    entry_contents : dict[str, dict]
        Mapping of entry_id to content.

    Returns
    -------
    list[Document]
        LangChain documents for RAGAS.
    """
    docs = []
    for target in targets:
        entry_id = target["entry_id"]
        content = entry_contents.get(entry_id)

        if not content:
            click.echo(f"  Warning: Entry {entry_id} not found in DB, skipping")
            continue

        # Use filtered_content if available, otherwise full_content
        body = content["filtered_content"] or content["full_content"]
        if not body:
            click.echo(f"  Warning: Entry {entry_id} has no content, skipping")
            continue

        # Format as Markdown with title heading for RAGAS
        title = content["title"]
        markdown_content = f"# {title}\n\n{body}"

        doc = Document(
            page_content=markdown_content,
            metadata={
                "entry_id": entry_id,
                "title": title,
                "url": content["url"],
                "language": target["language"],
                "feed_name": target.get("feed_name"),
                "category": target.get("category"),
            },
        )
        docs.append(doc)

    return docs


def create_custom_transforms(llm, embedding_model):
    """
    Create custom transforms without HeadlineSplitter.

    Uses the medium-document approach from RAGAS that doesn't rely on
    headline extraction and splitting, which can fail for documents
    without proper markdown heading structure.

    Parameters
    ----------
    llm : BaseRagasLLM
        LLM wrapper for text generation.
    embedding_model : BaseRagasEmbeddings
        Embedding model wrapper.

    Returns
    -------
    list
        List of transforms to apply.
    """

    def filter_doc_with_num_tokens(node, min_num_tokens=100):
        return (
            node.type == NodeType.DOCUMENT
            and num_tokens_from_string(node.properties.get("page_content", "")) > min_num_tokens
        )

    def filter_docs(node):
        return node.type == NodeType.DOCUMENT

    # Use medium-document transforms (without HeadlineSplitter)
    summary_extractor = SummaryExtractor(
        llm=llm, filter_nodes=lambda node: filter_doc_with_num_tokens(node, 100)
    )
    summary_emb_extractor = EmbeddingExtractor(
        embedding_model=embedding_model,
        property_name="summary_embedding",
        embed_property_name="summary",
        filter_nodes=lambda node: filter_doc_with_num_tokens(node, 100),
    )
    cosine_sim_builder = CosineSimilarityBuilder(
        property_name="summary_embedding",
        new_property_name="summary_similarity",
        threshold=0.5,
        filter_nodes=lambda node: filter_doc_with_num_tokens(node, 100),
    )
    ner_extractor = NERExtractor(llm=llm)
    ner_overlap_sim = OverlapScoreBuilder(threshold=0.01)
    theme_extractor = ThemesExtractor(llm=llm, filter_nodes=lambda node: filter_docs(node))
    node_filter = CustomNodeFilter(llm=llm)

    return [
        summary_extractor,
        node_filter,
        Parallel(summary_emb_extractor, theme_extractor, ner_extractor),
        Parallel(cosine_sim_builder, ner_overlap_sim),
    ]


async def create_query_distribution(
    llm,
    query_language: str,
):
    """
    Create query distribution with language-adapted prompts.

    Parameters
    ----------
    llm : BaseRagasLLM
        LLM wrapper for text generation.
    query_language : str
        Language code for generated questions ('en' or 'ja').

    Returns
    -------
    list
        Query distribution with adapted synthesizer.
    """
    synthesizer = SingleHopSpecificQuerySynthesizer(llm=llm)

    # Adapt prompts to target language
    language_name = LANGUAGE_NAMES.get(query_language, "english")
    prompts = await synthesizer.adapt_prompts(language_name, llm=llm)
    synthesizer.set_prompts(**prompts)

    return [(synthesizer, 1.0)]


def generate_qa_for_pattern(
    docs: list[Document],
    dataset_size: int,
    entry_language: str,
    query_language: str,
    llm_model: str,
    embedding_model: str,
) -> list[dict]:
    """
    Generate QA dataset for a specific language pattern using RAGAS.

    Parameters
    ----------
    docs : list[Document]
        List of LangChain documents.
    dataset_size : int
        Number of test samples to generate.
    entry_language : str
        Language code of source entries ('en' or 'ja').
    query_language : str
        Language code for generated questions ('en' or 'ja').
    llm_model : str
        LLM model name for generation.
    embedding_model : str
        Embedding model name.

    Returns
    -------
    list[dict]
        Generated QA samples with entry_id.
    """
    pattern = f"{entry_language}_{query_language}"
    click.echo(f"\nGenerating {dataset_size} samples for pattern {pattern}...")
    click.echo(f"  Entry language: {entry_language}, Query language: {query_language}")
    click.echo(f"  Using {len(docs)} documents")
    click.echo(f"  LLM: {llm_model}, Embedding: {embedding_model}")

    if not docs:
        click.echo("  No documents available, skipping")
        return []

    # Adjust dataset_size if we have fewer documents
    actual_size = min(dataset_size, len(docs))
    if actual_size < dataset_size:
        click.echo(f"  Adjusted dataset_size to {actual_size} (limited by doc count)")

    # Setup LLM and embeddings
    openai_client = OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        timeout=120.0,
        max_retries=3,
    )
    generator_llm = llm_factory(llm_model, client=openai_client)
    generator_embeddings = HuggingFaceEmbeddings(model=embedding_model)

    # Create custom transforms that skip HeadlineSplitter
    transforms = create_custom_transforms(generator_llm, generator_embeddings)

    # Create language-adapted query distribution if needed
    query_distribution = None
    if query_language != "en":
        query_distribution = asyncio.run(create_query_distribution(generator_llm, query_language))

    # Create generator
    generator = TestsetGenerator(
        llm=generator_llm,  # type: ignore[arg-type]
        embedding_model=generator_embeddings,  # type: ignore[arg-type]
    )

    # Generate dataset with custom transforms and optional query distribution
    if query_distribution:
        dataset = generator.generate_with_langchain_docs(
            docs,
            testset_size=actual_size,
            transforms=transforms,
            query_distribution=query_distribution,  # type: ignore[arg-type]
        )
    else:
        dataset = generator.generate_with_langchain_docs(
            docs,
            testset_size=actual_size,
            transforms=transforms,
        )

    # Convert to list of dicts
    df = dataset.to_pandas()  # type: ignore[union-attr]
    samples = df.to_dict(orient="records")

    # Build title -> entry_id mapping from docs
    title_to_entry_id = {doc.metadata["title"]: doc.metadata["entry_id"] for doc in docs}

    # Add metadata for each sample
    for sample in samples:
        sample["entry_language"] = entry_language
        sample["query_language"] = query_language
        sample["pattern"] = pattern

        # Extract entry_ids from reference_contexts
        entry_ids = []
        contexts = sample.get("reference_contexts", [])
        for ctx in contexts:
            # Context starts with "# {title}\n\n{body}"
            if ctx.startswith("# "):
                first_line = ctx.split("\n")[0]
                title = first_line[2:].strip()  # Remove "# " prefix
                if title in title_to_entry_id:
                    entry_id = title_to_entry_id[title]
                    if entry_id not in entry_ids:
                        entry_ids.append(entry_id)
        sample["entry_ids"] = entry_ids

    click.echo(f"  Generated {len(samples)} samples")
    return samples


@click.group(cls=OrderedGroup)
@click.option(
    "--dataset-name",
    default="singlehop-evaluation",
    help="Dataset name for directory (default: singlehop-evaluation)",
)
@click.pass_context
def cli(ctx, dataset_name: str):
    """Generate single-hop evaluation dataset for Research Agent."""
    ctx.ensure_object(dict)
    ctx.obj["dataset_name"] = dataset_name
    ctx.obj["output_dir"] = Path("evaluation") / dataset_name / "data"


@cli.command("sample")
@click.option(
    "--n-samples",
    default=15,
    help="Number of entries to sample per language (default: 15)",
)
@click.option(
    "--min-content-length",
    default=1000,
    help="Minimum content length for entries (default: 1000)",
)
@click.pass_context
def sample_cmd(ctx, n_samples: int, min_content_length: int):
    """Step 1: Sample diverse entries from database using K-means clustering."""
    output_dir: Path = ctx.obj["output_dir"]

    click.echo("=" * 60)
    click.echo("Step 1: Sampling entries from database")
    click.echo("=" * 60)

    conn = get_database_connection()

    try:
        click.echo(f"Fetching entries with embeddings (min length: {min_content_length})...")
        entries = fetch_entries_with_embeddings(conn, min_content_length)
        click.echo(f"  Found {len(entries)} entries")

        en_count = sum(1 for e in entries if e["language"] == "en")
        ja_count = sum(1 for e in entries if e["language"] == "ja")
        click.echo(f"  English: {en_count}, Japanese: {ja_count}")

        click.echo(f"\nSampling {n_samples} entries per language...")
        en_samples = sample_diverse_entries(entries, n_samples, "en")
        ja_samples = sample_diverse_entries(entries, n_samples, "ja")
        click.echo(f"  Sampled: English {len(en_samples)}, Japanese {len(ja_samples)}")

        def entry_to_eval_target(e):
            return {
                "entry_id": e["id"],
                "title": e["title"],
                "url": e["url"],
                "feed_name": e["feed_name"],
                "category": e["category_name"],
                "language": e["language"],
            }

        en_output = [entry_to_eval_target(e) for e in en_samples]
        ja_output = [entry_to_eval_target(e) for e in ja_samples]

        eval_targets = {
            "description": "Evaluation target entries (sampled by embedding diversity)",
            "sampling_params": {
                "n_samples_per_language": n_samples,
                "min_content_length": min_content_length,
            },
            "entries": {
                "en": en_output,
                "ja": ja_output,
            },
        }

        output_dir.mkdir(parents=True, exist_ok=True)
        targets_path = output_dir / "eval_targets.json"
        with open(targets_path, "w", encoding="utf-8") as f:
            json.dump(eval_targets, f, ensure_ascii=False, indent=2)

        click.echo(f"\nSaved to {targets_path}")

    finally:
        conn.close()


@cli.command("generate")
@click.option(
    "--dataset-size",
    default=10,
    help="Number of QA samples per pattern (default: 10)",
)
@click.option(
    "--llm-model",
    default=None,
    help="LLM model for generation (default: $EVAL_DATA_LLM_MODEL or gpt-4o-mini)",
)
@click.option(
    "--embedding-model",
    default=None,
    help="Embedding model (default: $EVAL_DATA_EMBEDDING_LLM_MODEL)",
)
@click.pass_context
def generate_cmd(
    ctx,
    dataset_size: int,
    llm_model: str | None,
    embedding_model: str | None,
):
    """Step 2: Generate QA pairs with RAGAS TestsetGenerator."""
    output_dir: Path = ctx.obj["output_dir"]
    targets_path = output_dir / "eval_targets.json"

    if not targets_path.exists():
        raise click.ClickException(f"{targets_path} not found. Run 'sample' command first.")

    # Get model from env if not specified
    if llm_model is None:
        llm_model = os.environ.get("EVAL_DATA_LLM_MODEL", "gpt-4o-mini")
    if embedding_model is None:
        embedding_model = os.environ.get(
            "EVAL_DATA_EMBEDDING_LLM_MODEL",
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        )

    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        raise click.ClickException(
            "OPENAI_API_KEY environment variable not set. "
            "Run with: op run --env-file=.env.op -- ..."
        )

    click.echo("=" * 60)
    click.echo("Step 2: Generating QA pairs with RAGAS")
    click.echo("=" * 60)
    click.echo(f"  LLM: {llm_model}")
    click.echo(f"  Embedding: {embedding_model}")

    # Load targets
    with open(targets_path, encoding="utf-8") as f:
        targets = json.load(f)

    en_targets = targets["entries"]["en"]
    ja_targets = targets["entries"]["ja"]
    click.echo(f"  English entries: {len(en_targets)}")
    click.echo(f"  Japanese entries: {len(ja_targets)}")

    conn = get_database_connection()

    try:
        # Fetch content
        click.echo("\nFetching entry content from database...")
        all_entry_ids = [t["entry_id"] for t in en_targets + ja_targets]
        entry_contents = fetch_entry_content(conn, all_entry_ids)
        click.echo(f"  Fetched {len(entry_contents)} entries")

        # Create documents
        en_docs = create_documents(en_targets, entry_contents)
        ja_docs = create_documents(ja_targets, entry_contents)
        click.echo(f"  Created documents: English {len(en_docs)}, Japanese {len(ja_docs)}")

        # Generate datasets for 4 patterns
        results: dict[str, list] = {
            "en_en": [],
            "en_ja": [],
            "ja_en": [],
            "ja_ja": [],
        }

        patterns = [
            ("en", "en", en_docs),
            ("en", "ja", en_docs),
            ("ja", "en", ja_docs),
            ("ja", "ja", ja_docs),
        ]

        for entry_lang, query_lang, docs in patterns:
            pattern_key = f"{entry_lang}_{query_lang}"
            if docs:
                samples = generate_qa_for_pattern(
                    docs,
                    dataset_size,
                    entry_lang,
                    query_lang,
                    llm_model,
                    embedding_model,
                )
                results[pattern_key] = samples

        # Save results
        qa_dir = output_dir / "qa"
        qa_dir.mkdir(parents=True, exist_ok=True)

        output = {
            "generated_at": datetime.now().isoformat(),
            "llm_model": llm_model,
            "embedding_model": embedding_model,
            "dataset_size_requested": dataset_size,
            "patterns": {
                "en_en": "English Entry -> English Question",
                "en_ja": "English Entry -> Japanese Question",
                "ja_en": "Japanese Entry -> English Question",
                "ja_ja": "Japanese Entry -> Japanese Question",
            },
            "qa_samples": results,
        }

        qa_path = qa_dir / "eval_qa.json"
        with open(qa_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2, default=str)

        # Print summary
        click.echo(f"\n{'=' * 60}")
        click.echo("Generation Summary")
        click.echo("=" * 60)
        total = 0
        for pattern_key, samples in results.items():
            count = len(samples)
            total += count
            click.echo(f"  {pattern_key}: {count} QA pairs")
        click.echo(f"  Total: {total} QA pairs")
        click.echo(f"\nSaved to {qa_path}")

    finally:
        conn.close()


@cli.command("upload")
@click.option(
    "--langfuse-dataset-name",
    default=None,
    help="Langfuse dataset name (default: same as --dataset-name)",
)
@click.pass_context
def upload_cmd(ctx, langfuse_dataset_name: str | None):
    """Step 3: Upload generated QA pairs to Langfuse Dataset."""
    output_dir: Path = ctx.obj["output_dir"]
    dataset_name: str = ctx.obj["dataset_name"]
    targets_path = output_dir / "eval_targets.json"
    qa_path = output_dir / "qa" / "eval_qa.json"

    if not targets_path.exists():
        raise click.ClickException(f"{targets_path} not found. Run 'sample' command first.")
    if not qa_path.exists():
        raise click.ClickException(f"{qa_path} not found. Run 'generate' command first.")

    click.echo("=" * 60)
    click.echo("Step 3: Uploading to Langfuse Dataset")
    click.echo("=" * 60)

    # Load data
    with open(targets_path, encoding="utf-8") as f:
        targets = json.load(f)
    with open(qa_path, encoding="utf-8") as f:
        qa_data = json.load(f)

    qa_results = qa_data.get("qa_samples", {})

    # Build entry_id -> metadata mapping
    entry_metadata = {}
    for lang in ["en", "ja"]:
        for target in targets["entries"].get(lang, []):
            entry_metadata[target["entry_id"]] = {
                "title": target.get("title"),
                "url": target.get("url"),
                "feed_name": target.get("feed_name"),
                "category": target.get("category"),
            }

    # Initialize Langfuse client
    langfuse = get_langfuse_client()

    # Determine dataset name
    target_dataset_name = langfuse_dataset_name or dataset_name
    click.echo(f"\nUploading to dataset: {target_dataset_name}")

    # Create or get dataset
    try:
        langfuse.get_dataset(target_dataset_name)
        click.echo(f"  Found existing dataset: {target_dataset_name}")
    except Exception:
        langfuse.create_dataset(
            name=target_dataset_name,
            description="Single-hop evaluation dataset for Research Agent (RAGAS)",
            metadata={
                "created_by": "generate-singlehop-eval-dataset",
                "created_at": datetime.now().isoformat(),
            },
        )
        click.echo(f"  Created new dataset: {target_dataset_name}")

    # Upload items for each pattern
    total_uploaded = 0
    for pattern, samples in qa_results.items():
        click.echo(f"  Uploading {len(samples)} items for pattern {pattern}...")

        for i, sample in enumerate(samples):
            question = sample.get("user_input", sample.get("question", ""))
            answer = sample.get("reference", sample.get("ground_truth", ""))

            if not question:
                continue

            entry_ids = sample.get("entry_ids", [])

            # Build metadata
            metadata = {
                "pattern": pattern,
                "entry_language": sample.get("entry_language"),
                "query_language": sample.get("query_language"),
                "source_entry_ids": entry_ids,
                "synthesizer_name": sample.get("synthesizer_name", ""),
            }

            # Remove None values
            metadata = {k: v for k, v in metadata.items() if v is not None}

            # Add entry metadata if available
            source_entries = []
            for entry_id in entry_ids:
                if entry_id in entry_metadata:
                    source_entries.append(entry_metadata[entry_id])
            if source_entries:
                metadata["source_entries"] = source_entries

            try:
                langfuse.create_dataset_item(
                    dataset_name=target_dataset_name,
                    input={"question": question},
                    expected_output={"answer": answer} if answer else None,
                    metadata=metadata,
                )
                total_uploaded += 1
            except Exception as e:
                click.echo(f"    Error uploading sample {i + 1}: {e}")

    langfuse.flush()

    click.echo(f"\n{'=' * 60}")
    click.echo("Upload Summary")
    click.echo("=" * 60)
    click.echo(f"  Dataset: {target_dataset_name}")
    click.echo(f"  Total uploaded: {total_uploaded}")


@cli.command("all")
@click.option(
    "--n-samples",
    default=15,
    help="Number of entries to sample per language (default: 15)",
)
@click.option(
    "--min-content-length",
    default=1000,
    help="Minimum content length for entries (default: 1000)",
)
@click.option(
    "--dataset-size",
    default=10,
    help="Number of QA samples per pattern (default: 10)",
)
@click.option(
    "--llm-model",
    default=None,
    help="LLM model for generation (default: $EVAL_DATA_LLM_MODEL or gpt-4o-mini)",
)
@click.pass_context
def all_cmd(
    ctx,
    n_samples: int,
    min_content_length: int,
    dataset_size: int,
    llm_model: str | None,
):
    """Run all steps: sample -> generate -> upload."""
    ctx.invoke(sample_cmd, n_samples=n_samples, min_content_length=min_content_length)
    ctx.invoke(generate_cmd, dataset_size=dataset_size, llm_model=llm_model)
    ctx.invoke(upload_cmd)


if __name__ == "__main__":
    cli()
