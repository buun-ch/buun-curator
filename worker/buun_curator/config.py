"""
Configuration management for Buun Curator Backend.
"""

import os
from dataclasses import dataclass


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.
    """

    # API Server
    api_url: str  # REST API base URL
    api_token: str  # Internal API token for authentication

    # OpenAI / LLM (set OPENAI_BASE_URL for LiteLLM proxy, leave empty for OpenAI direct)
    openai_api_key: str
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

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.
        """
        return cls(
            api_url=os.getenv("BUUN_CURATOR_API_URL", "http://localhost:3000"),
            api_token=os.getenv("INTERNAL_API_TOKEN", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            openai_base_url=os.getenv("OPENAI_BASE_URL", ""),  # Empty = OpenAI direct
            # LLM models with fallback chain
            llm_model=(llm_default := os.getenv("LLM_MODEL", "claude-haiku")),
            extraction_llm_model=os.getenv("EXTRACTION_LLM_MODEL", "") or llm_default,
            reasoning_llm_model=os.getenv("REASONING_LLM_MODEL", "") or llm_default,
            summarization_llm_model=os.getenv("SUMMARIZATION_LLM_MODEL", "") or llm_default,
            translation_provider=os.getenv("TRANSLATION_PROVIDER", "deepl"),
            deepl_api_key=os.getenv("DEEPL_API_KEY", ""),
            ms_translator_subscription_key=os.getenv("MS_TRANSLATOR_SUBSCRIPTION_KEY", ""),
            ms_translator_region=os.getenv("MS_TRANSLATOR_REGION", ""),
            temporal_host=os.getenv("TEMPORAL_HOST", "localhost:7233"),
            temporal_namespace=os.getenv("TEMPORAL_NAMESPACE", "default"),
            task_queue=os.getenv("TEMPORAL_TASK_QUEUE", "buun-curator"),
            enable_content_fetch=os.getenv("ENABLE_CONTENT_FETCH", "true").lower() == "true",
            enable_summarization=os.getenv("ENABLE_SUMMARIZATION", "true").lower() == "true",
            enable_thumbnail=os.getenv("ENABLE_THUMBNAIL", "true").lower() == "true",
            s3_endpoint=os.getenv("S3_ENDPOINT", ""),  # Empty for AWS S3
            s3_access_key=os.getenv("S3_ACCESS_KEY", ""),
            s3_secret_key=os.getenv("S3_SECRET_KEY", ""),
            s3_bucket=os.getenv("S3_BUCKET", "buun-curator"),
            s3_prefix=os.getenv("S3_PREFIX", ""),  # e.g., "public"
            s3_public_url=os.getenv("S3_PUBLIC_URL", ""),
            s3_region=os.getenv("S3_REGION", "us-east-1"),
            github_token=os.getenv("GITHUB_TOKEN", ""),
            feed_ingestion_concurrency=int(os.getenv("FEED_INGESTION_CONCURRENCY", "5")),
            fetch_concurrency=int(os.getenv("FETCH_CONCURRENCY", "3")),
            # Worker concurrency limits (0 = use Temporal defaults)
            max_concurrent_activities=int(os.getenv("MAX_CONCURRENT_ACTIVITIES", "0")),
            max_concurrent_workflow_tasks=int(os.getenv("MAX_CONCURRENT_WORKFLOW_TASKS", "0")),
            max_concurrent_local_activities=int(
                os.getenv("MAX_CONCURRENT_LOCAL_ACTIVITIES", "0")
            ),
            domain_fetch_delay=float(os.getenv("DOMAIN_FETCH_DELAY", "2.0")),
            graph_rag_backend=os.getenv("GRAPH_RAG_BACKEND", "graphiti"),
            # Langfuse
            langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            langfuse_host=os.getenv("LANGFUSE_HOST", ""),
            # AI Evaluation
            ai_evaluation_enabled=os.getenv("AI_EVALUATION_ENABLED", "false").lower()
            == "true",
            # Embedding models
            graphrag_embedding_model=os.getenv(
                "GRAPHRAG_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
            ),
            evaluation_embedding_model=os.getenv(
                "EVALUATION_EMBEDDING_MODEL",
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            ),
            max_content_chars=int(os.getenv("MAX_CONTENT_CHARS", "500000")),
            max_entry_age_days=int(os.getenv("MAX_ENTRY_AGE_DAYS", "7")),
        )


# Global config instance (lazy loaded)
_config: Config | None = None


def get_config() -> Config:
    """
    Get the global configuration instance.
    """
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
