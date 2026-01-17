"""
Embedding Service for Agent.

Provides text embedding using sentence-transformers for semantic search.
Uses the same model as worker for consistency.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from buun_curator_agent.logging import get_logger

logger = get_logger(__name__)

# Module-level cache for embedding model
_model: Any = None
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_EMBEDDING_DIM = 768

# Thread pool for CPU-bound embedding computation
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedder")


def _get_model() -> Any:
    """
    Get or initialize the sentence-transformers model.

    Returns
    -------
    SentenceTransformer
        Model instance.
    """
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model", model_name=_MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded", model_name=_MODEL_NAME)
    return _model


def _compute_embedding_sync(text: str) -> list[float]:
    """
    Synchronous embedding computation (runs in thread pool).

    Parameters
    ----------
    text : str
        Text to embed.

    Returns
    -------
    list[float]
        768-dimensional embedding vector.
    """
    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


async def compute_query_embedding(query: str) -> list[float]:
    """
    Compute embedding for a query text.

    Runs in a thread pool to avoid blocking the event loop.

    Parameters
    ----------
    query : str
        Query text to embed.

    Returns
    -------
    list[float]
        768-dimensional embedding vector.
    """
    if not query.strip():
        raise ValueError("Query text cannot be empty")

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _compute_embedding_sync, query)
