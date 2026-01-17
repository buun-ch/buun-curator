"""
LightRAG module for Buun Curator.

Provides LightRAG-based knowledge graph functionality with Memgraph storage.
"""

from buun_curator.lightrag.embedder import (
    FastEmbedConfig,
    get_lightrag_embedding_func,
    lightrag_embedding_func,
)
from buun_curator.lightrag.global_graph import (
    add_content_to_global_graph,
    add_contents_bulk_to_global_graph,
    reset_global_lightrag,
    search_global_graph,
)
from buun_curator.lightrag.llm import get_llm_config, lightrag_llm_func

__all__ = [
    # LLM
    "get_llm_config",
    "lightrag_llm_func",
    # Embedder
    "FastEmbedConfig",
    "get_lightrag_embedding_func",
    "lightrag_embedding_func",
    # Global graph
    "add_content_to_global_graph",
    "add_contents_bulk_to_global_graph",
    "search_global_graph",
    "reset_global_lightrag",
]
