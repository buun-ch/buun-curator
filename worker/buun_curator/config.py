"""
Configuration management for Buun Curator Backend.
"""

import os
from dataclasses import dataclass


def get_env(name: str, default: str | None) -> str:
    """
    Get environment variable value.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : str | None
        Default value if not set. If None, the variable is required.

    Returns
    -------
    str
        Environment variable value.

    Raises
    ------
    ValueError
        If default is None and variable is not set.
    """
    value = os.getenv(name)
    if value is None:
        if default is None:
            raise ValueError(f"Required environment variable '{name}' is not set")
        return default
    return value


def get_env_bool(name: str, default: bool | None) -> bool:
    """
    Get boolean environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : bool | None
        Default value if not set. If None, the variable is required.

    Returns
    -------
    bool
        True if value is "true" (case-insensitive), False otherwise.

    Raises
    ------
    ValueError
        If default is None and variable is not set.
    """
    str_default = str(default) if default is not None else None
    return get_env(name, str_default).lower() == "true"


def get_env_int(name: str, default: int | None) -> int:
    """
    Get integer environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : int | None
        Default value if not set. If None, the variable is required.

    Returns
    -------
    int
        Parsed integer value.

    Raises
    ------
    ValueError
        If default is None and variable is not set.
    """
    str_default = str(default) if default is not None else None
    return int(get_env(name, str_default))


def get_env_float(name: str, default: float | None) -> float:
    """
    Get float environment variable.

    Parameters
    ----------
    name : str
        Environment variable name.
    default : float | None
        Default value if not set. If None, the variable is required.

    Returns
    -------
    float
        Parsed float value.

    Raises
    ------
    ValueError
        If default is None and variable is not set.
    """
    str_default = str(default) if default is not None else None
    return float(get_env(name, str_default))


# =============================================================================
# Default values
# =============================================================================

# API
DEFAULT_API_URL = "http://localhost:3000"

# LLM
DEFAULT_LLM_MODEL = "claude-haiku"

# Translation
DEFAULT_TRANSLATION_PROVIDER = "deepl"

# Temporal
DEFAULT_TEMPORAL_HOST = "localhost:7233"
DEFAULT_TEMPORAL_NAMESPACE = "default"
DEFAULT_TASK_QUEUE = "buun-curator"

# Feature flags
DEFAULT_ENABLE_CONTENT_FETCH = True
DEFAULT_ENABLE_SUMMARIZATION = True
DEFAULT_ENABLE_THUMBNAIL = True

# S3
DEFAULT_S3_BUCKET = "buun-curator"
DEFAULT_S3_REGION = "us-east-1"

# Concurrency
DEFAULT_FEED_INGESTION_CONCURRENCY = 5
DEFAULT_FETCH_CONCURRENCY = 3
DEFAULT_MAX_CONCURRENT_ACTIVITIES = 0
DEFAULT_MAX_CONCURRENT_WORKFLOW_TASKS = 0
DEFAULT_MAX_CONCURRENT_LOCAL_ACTIVITIES = 0

# Rate limiting
DEFAULT_DOMAIN_FETCH_DELAY = 2.0

# GraphRAG
DEFAULT_GRAPH_RAG_BACKEND = "graphiti"
DEFAULT_GRAPHRAG_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_EVALUATION_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# Content processing
DEFAULT_MAX_CONTENT_CHARS = 500000
DEFAULT_MAX_ENTRY_AGE_DAYS = 7

# Batch sizes
DEFAULT_DISTILLATION_BATCH_SIZE = 5
DEFAULT_SEARCH_REINDEX_BATCH_SIZE = 500
DEFAULT_SEARCH_PRUNE_BATCH_SIZE = 1000
DEFAULT_GRAPH_REBUILD_BATCH_SIZE = 50
DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE = 50
DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE = 100

# AI Evaluation
DEFAULT_AI_EVALUATION_ENABLED = False


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # API Server
    api_url: str  # REST API base URL
    api_token: str  # Internal API token for authentication (required)

    # OpenAI / LLM (set OPENAI_BASE_URL for LiteLLM proxy, leave empty for OpenAI direct)
    openai_api_key: str  # Required
    openai_base_url: str

    # === LLM Model Configuration ===
    #
    # Default model (fallback for all tasks)
    llm_model: str

    # --- Task-specific models (if empty, falls back to llm_model) ---
    #
    # EXTRACTION: Context extraction from entries
    # - Requires: Structured Output support (complex nested schema)
    # - Note: Claude Haiku does NOT support Structured Output
    #   https://docs.langchain.com/oss/python/integrations/chat/anthropic#structured-output
    extraction_llm_model: str

    # REASONING: GitHub reranking, decision making
    # - Requires: Structured Output support (simple schema), good reasoning
    reasoning_llm_model: str

    # SUMMARIZATION: Entry summarization
    # - Requires: Good text comprehension and generation
    summarization_llm_model: str

    # Translation
    translation_provider: str  # "microsoft" or "deepl"

    # DeepL
    deepl_api_key: str

    # Microsoft Translator
    ms_translator_subscription_key: str
    ms_translator_region: str

    # Temporal
    temporal_host: str
    temporal_namespace: str
    task_queue: str

    # Feature flags
    enable_content_fetch: bool
    enable_summarization: bool
    enable_thumbnail: bool

    # S3 / MinIO compatible storage
    s3_endpoint: str  # Empty string for AWS S3, URL for MinIO/other S3-compatible
    s3_access_key: str
    s3_secret_key: str
    s3_bucket: str
    s3_prefix: str  # Object key prefix (e.g., "public" or "public/thumbnails")
    s3_public_url: str  # Public URL for accessing thumbnails
    s3_region: str  # AWS region (default: us-east-1)

    # GitHub API
    github_token: str  # Optional: increases rate limit from 60 to 5000 requests/hour

    # Workflow concurrency
    feed_ingestion_concurrency: int  # Max concurrent child workflows for feed ingestion

    # Activity concurrency
    fetch_concurrency: int  # Max concurrent HTTP fetch requests per activity

    # Worker concurrency limits (Temporal worker configuration)
    max_concurrent_activities: int  # Max concurrent activity tasks (0 = unlimited)
    max_concurrent_workflow_tasks: int  # Max concurrent workflow tasks (0 = unlimited)
    max_concurrent_local_activities: int  # Max concurrent local activities (0 = unlimited)

    # Rate limiting
    domain_fetch_delay: float  # Delay between requests to same domain (seconds)

    # GraphRAG backend: "graphiti" or "lightrag"
    graph_rag_backend: str

    # Langfuse (direct connection for RAGAS score recording)
    langfuse_public_key: str
    langfuse_secret_key: str
    langfuse_host: str

    # AI Evaluation
    ai_evaluation_enabled: bool

    # Embedding models
    graphrag_embedding_model: str  # For GraphRAG (graphiti, lightrag)
    evaluation_embedding_model: str  # For RAGAS evaluation

    # Content processing
    max_content_chars: int  # Max chars for LLM content processing (0 = no limit)

    # Entry age filtering
    max_entry_age_days: int  # Skip entries older than this (0 = no limit)

    # Content distillation
    distillation_batch_size: int  # Batch size for LLM distillation

    # Admin workflow batch sizes
    search_reindex_batch_size: int  # Batch size for Meilisearch reindex
    search_prune_batch_size: int  # Batch size for search prune
    graph_rebuild_batch_size: int  # Batch size for graph rebuild
    global_graph_update_batch_size: int  # Batch size for graph update
    embedding_backfill_batch_size: int  # Batch size for embedding backfill

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # LLM model with fallback chain
        llm_model = get_env("LLM_MODEL", DEFAULT_LLM_MODEL)

        return cls(
            # API (token is required)
            api_url=get_env("BUUN_CURATOR_API_URL", DEFAULT_API_URL),
            api_token=get_env("INTERNAL_API_TOKEN", None),
            # OpenAI / LLM (API key is required)
            openai_api_key=get_env("OPENAI_API_KEY", None),
            openai_base_url=get_env("OPENAI_BASE_URL", ""),
            # LLM models
            llm_model=llm_model,
            extraction_llm_model=get_env("EXTRACTION_LLM_MODEL", "") or llm_model,
            reasoning_llm_model=get_env("REASONING_LLM_MODEL", "") or llm_model,
            summarization_llm_model=get_env("SUMMARIZATION_LLM_MODEL", "") or llm_model,
            # Translation
            translation_provider=get_env("TRANSLATION_PROVIDER", DEFAULT_TRANSLATION_PROVIDER),
            deepl_api_key=get_env("DEEPL_API_KEY", ""),
            ms_translator_subscription_key=get_env("MS_TRANSLATOR_SUBSCRIPTION_KEY", ""),
            ms_translator_region=get_env("MS_TRANSLATOR_REGION", ""),
            # Temporal
            temporal_host=get_env("TEMPORAL_HOST", DEFAULT_TEMPORAL_HOST),
            temporal_namespace=get_env("TEMPORAL_NAMESPACE", DEFAULT_TEMPORAL_NAMESPACE),
            task_queue=get_env("TEMPORAL_TASK_QUEUE", DEFAULT_TASK_QUEUE),
            # Feature flags
            enable_content_fetch=get_env_bool("ENABLE_CONTENT_FETCH", DEFAULT_ENABLE_CONTENT_FETCH),
            enable_summarization=get_env_bool("ENABLE_SUMMARIZATION", DEFAULT_ENABLE_SUMMARIZATION),
            enable_thumbnail=get_env_bool("ENABLE_THUMBNAIL", DEFAULT_ENABLE_THUMBNAIL),
            # S3
            s3_endpoint=get_env("S3_ENDPOINT", ""),
            s3_access_key=get_env("S3_ACCESS_KEY", ""),
            s3_secret_key=get_env("S3_SECRET_KEY", ""),
            s3_bucket=get_env("S3_BUCKET", DEFAULT_S3_BUCKET),
            s3_prefix=get_env("S3_PREFIX", ""),
            s3_public_url=get_env("S3_PUBLIC_URL", ""),
            s3_region=get_env("S3_REGION", DEFAULT_S3_REGION),
            # GitHub
            github_token=get_env("GITHUB_TOKEN", ""),
            # Concurrency
            feed_ingestion_concurrency=get_env_int(
                "FEED_INGESTION_CONCURRENCY", DEFAULT_FEED_INGESTION_CONCURRENCY
            ),
            fetch_concurrency=get_env_int("FETCH_CONCURRENCY", DEFAULT_FETCH_CONCURRENCY),
            max_concurrent_activities=get_env_int(
                "MAX_CONCURRENT_ACTIVITIES", DEFAULT_MAX_CONCURRENT_ACTIVITIES
            ),
            max_concurrent_workflow_tasks=get_env_int(
                "MAX_CONCURRENT_WORKFLOW_TASKS", DEFAULT_MAX_CONCURRENT_WORKFLOW_TASKS
            ),
            max_concurrent_local_activities=get_env_int(
                "MAX_CONCURRENT_LOCAL_ACTIVITIES", DEFAULT_MAX_CONCURRENT_LOCAL_ACTIVITIES
            ),
            # Rate limiting
            domain_fetch_delay=get_env_float("DOMAIN_FETCH_DELAY", DEFAULT_DOMAIN_FETCH_DELAY),
            # GraphRAG
            graph_rag_backend=get_env("GRAPH_RAG_BACKEND", DEFAULT_GRAPH_RAG_BACKEND),
            # Langfuse
            langfuse_public_key=get_env("LANGFUSE_PUBLIC_KEY", ""),
            langfuse_secret_key=get_env("LANGFUSE_SECRET_KEY", ""),
            langfuse_host=get_env("LANGFUSE_HOST", ""),
            # AI Evaluation
            ai_evaluation_enabled=get_env_bool(
                "AI_EVALUATION_ENABLED", DEFAULT_AI_EVALUATION_ENABLED
            ),
            # Embedding models
            graphrag_embedding_model=get_env(
                "GRAPHRAG_EMBEDDING_MODEL", DEFAULT_GRAPHRAG_EMBEDDING_MODEL
            ),
            evaluation_embedding_model=get_env(
                "EVALUATION_EMBEDDING_MODEL", DEFAULT_EVALUATION_EMBEDDING_MODEL
            ),
            # Content processing
            max_content_chars=get_env_int("MAX_CONTENT_CHARS", DEFAULT_MAX_CONTENT_CHARS),
            max_entry_age_days=get_env_int("MAX_ENTRY_AGE_DAYS", DEFAULT_MAX_ENTRY_AGE_DAYS),
            # Batch sizes
            distillation_batch_size=get_env_int(
                "DISTILLATION_BATCH_SIZE", DEFAULT_DISTILLATION_BATCH_SIZE
            ),
            search_reindex_batch_size=get_env_int(
                "SEARCH_REINDEX_BATCH_SIZE", DEFAULT_SEARCH_REINDEX_BATCH_SIZE
            ),
            search_prune_batch_size=get_env_int(
                "SEARCH_PRUNE_BATCH_SIZE", DEFAULT_SEARCH_PRUNE_BATCH_SIZE
            ),
            graph_rebuild_batch_size=get_env_int(
                "GRAPH_REBUILD_BATCH_SIZE", DEFAULT_GRAPH_REBUILD_BATCH_SIZE
            ),
            global_graph_update_batch_size=get_env_int(
                "GLOBAL_GRAPH_UPDATE_BATCH_SIZE", DEFAULT_GLOBAL_GRAPH_UPDATE_BATCH_SIZE
            ),
            embedding_backfill_batch_size=get_env_int(
                "EMBEDDING_BACKFILL_BATCH_SIZE", DEFAULT_EMBEDDING_BACKFILL_BATCH_SIZE
            ),
        )


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
