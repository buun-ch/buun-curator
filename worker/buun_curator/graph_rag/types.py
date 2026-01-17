"""Common types for GraphRAG backends."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class GraphRAGBackend(str, Enum):
    """Supported GraphRAG backends."""

    GRAPHITI = "graphiti"
    LIGHTRAG = "lightrag"


class SearchMode(str, Enum):
    """
    Unified search mode abstraction based on LightRAG modes.

    Maps to backend-specific search types:
    - LightRAG: naive, local, global, hybrid, mix (native)
    - Graphiti: search() (all modes map to hybrid internally)
    """

    # Raw chunk/content search (vector similarity only)
    NAIVE = "naive"
    # Local context search (entity relationships)
    LOCAL = "local"
    # Global context search (summaries)
    GLOBAL = "global"
    # Hybrid search (graph + vector combined)
    HYBRID = "hybrid"
    # Mixed search (combination of local + global)
    MIX = "mix"


class SearchResult(BaseModel):
    """Unified search result format."""

    id: str
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    # Source information
    source_type: str = ""  # "entity", "relationship", "chunk", etc.
    # Backend-specific raw result (for debugging)
    raw: dict[str, Any] | None = None


class SessionState(BaseModel):
    """Persisted session state for recovery."""

    entry_id: str
    backend: GraphRAGBackend
    graph_name: str
    started: bool = False
    content_added: bool = False
    graph_built: bool = False
    # Backend-specific state
    backend_state: dict[str, Any] = Field(default_factory=dict)
