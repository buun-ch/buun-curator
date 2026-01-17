"""
Embedding Service for Buun Curator.

Provides text embedding using FastEmbed for recommendation scoring.
Separate from LightRAG's embedder to avoid confusion.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
from numpy.typing import NDArray

from buun_curator.logging import get_logger

logger = get_logger(__name__)

# Module-level cache for embedding model
_model: Any = None
_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
_EMBEDDING_DIM = 768

# Thread pool for CPU-bound embedding computation
# Using a single thread to avoid model loading issues
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedder")


def _get_model() -> Any:
    """
    Get or initialize the FastEmbed model.

    Returns
    -------
    TextEmbedding
        FastEmbed model instance.
    """
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        logger.info("Loading embedding model", model_name=_MODEL_NAME)
        _model = TextEmbedding(model_name=_MODEL_NAME)
        logger.info("Embedding model loaded")
    return _model


def _compute_embeddings_sync(texts: list[str]) -> NDArray[np.float32]:
    """
    Synchronous embedding computation (runs in thread pool).

    Parameters
    ----------
    texts : list[str]
        Texts to embed.

    Returns
    -------
    NDArray[np.float32]
        Array of shape (len(texts), 768) with embeddings.
    """
    model = _get_model()
    # FastEmbed's embed() returns a generator
    embeddings = list(model.embed(texts))
    return np.array(embeddings, dtype=np.float32)


async def compute_embeddings(texts: list[str]) -> NDArray[np.float32]:
    """
    Compute embeddings for a list of texts.

    Runs in a thread pool to avoid blocking the event loop,
    allowing health checks to respond during computation.

    Parameters
    ----------
    texts : list[str]
        Texts to embed.

    Returns
    -------
    NDArray[np.float32]
        Array of shape (len(texts), 768) with embeddings.
    """
    if not texts:
        return np.array([], dtype=np.float32)

    # Run CPU-bound embedding computation in thread pool
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _compute_embeddings_sync, texts)
