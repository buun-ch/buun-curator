"""Agent service configuration."""

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent service settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    # OpenAI
    openai_base_url: str = ""
    openai_api_key: SecretStr = SecretStr("")

    # Agent models
    research_model: str = ""
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

    # Search
    default_search_mode: str = "planner"  # planner, meilisearch, embedding, hybrid

    # API
    api_base_url: str = ""  # Next.js API base URL for fetching entry data
    internal_api_token: str = ""  # Token for authenticating internal API calls

    # CORS
    cors_origins: list[str] = []

    # Environment
    environment: str = "development"

    # Logging
    log_level: str = "INFO"

    # OpenTelemetry
    otel_tracing_enabled: bool = False
    otel_service_name: str = "buun-curator-agent"
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # Langfuse (direct connection)
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str | None = None  # e.g., https://cloud.langfuse.com

    # Evaluation
    ai_evaluation_enabled: bool = False

    # Temporal
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "default"
    temporal_task_queue: str = "buun-curator"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Convert log level to uppercase."""
        return v.upper()


settings = Settings()
