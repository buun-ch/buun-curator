"""
GraphRAG abstraction layer for multi-backend support.

Provides a unified interface for different GraphRAG backends:
- Cognee (default)
- Graphiti (planned)
- LightRAG (future)
"""

from buun_curator.graph_rag.base import GraphRAGSession
from buun_curator.graph_rag.types import (
    GraphRAGBackend,
    SearchMode,
    SearchResult,
    SessionState,
)

__all__ = [
    "GraphRAGBackend",
    "GraphRAGSession",
    "SearchMode",
    "SearchResult",
    "SessionState",
]
