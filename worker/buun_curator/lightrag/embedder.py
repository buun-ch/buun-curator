"""
FastEmbed-based embedder for LightRAG.

Provides a local embedding solution using FastEmbed, compatible with
LightRAG's EmbeddingFunc interface.
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# Default model and dimensions (same as Graphiti)
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_DIMENSIONS = 768
DEFAULT_MAX_TOKEN_SIZE = 8192


@dataclass
class FastEmbedConfig:
    """Configuration for FastEmbed embedder."""

    model: str = field(
        default_factory=lambda: os.getenv("GRAPHRAG_EMBEDDING_MODEL", DEFAULT_MODEL)
    )
    embedding_dim: int = field(
        default_factory=lambda: int(os.getenv("EMBEDDING_DIMENSIONS", str(DEFAULT_DIMENSIONS)))
    )
    threads: int | None = field(
        default_factory=lambda: (int(val) if (val := os.getenv("EMBEDDING_THREADS")) else None)
    )
    max_token_size: int = field(
        default_factory=lambda: int(
            os.getenv("EMBEDDING_MAX_TOKEN_SIZE", str(DEFAULT_MAX_TOKEN_SIZE))
        )
    )


# Global model instance for reuse
_fastembed_model = None
_fastembed_config: FastEmbedConfig | None = None


def _get_fastembed_model(config: FastEmbedConfig | None = None):
    """
    Get or create FastEmbed model instance (lazy loading).

    Parameters
    ----------
    config : FastEmbedConfig | None
        Configuration for the embedder. Uses defaults if not provided.

    Returns
    -------
    TextEmbedding
        Initialized FastEmbed model.
    """
    global _fastembed_model, _fastembed_config

    if config is None:
        config = FastEmbedConfig()

    if _fastembed_model is None or _fastembed_config != config:
        from fastembed import TextEmbedding

        logger.info(f"Loading FastEmbed model: {config.model}")
        kwargs: dict = {"model_name": config.model}
        if config.threads is not None:
            kwargs["threads"] = config.threads
            logger.info(f"FastEmbed using {config.threads} threads")

        _fastembed_model = TextEmbedding(**kwargs)
        _fastembed_config = config
        logger.info(f"FastEmbed model loaded: {config.model}")

    return _fastembed_model


async def lightrag_embedding_func(texts: list[str]) -> np.ndarray:
    """
    Embedding function for LightRAG using FastEmbed.

    This function is passed to LightRAG's embedding_func parameter.
    It uses FastEmbed for local, CPU-based embedding generation.

    Parameters
    ----------
    texts : list[str]
        List of texts to embed.

    Returns
    -------
    np.ndarray
        Array of embedding vectors with shape (len(texts), embedding_dim).
    """
    if not texts:
        config = FastEmbedConfig()
        return np.array([]).reshape(0, config.embedding_dim)

    model = _get_fastembed_model()

    # Run embedding in thread pool to avoid blocking async event loop
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(
        None,
        lambda: list(model.embed(texts)),
    )

    # Convert to numpy array
    result = np.array(embeddings)
    logger.debug(f"Generated embeddings for {len(texts)} texts, shape={result.shape}")
    return result


def get_lightrag_embedding_func():
    """
    Create LightRAG-compatible EmbeddingFunc wrapper.

    Returns
    -------
    EmbeddingFunc
        LightRAG embedding function configuration with proper dimensions.
    """
    from lightrag.utils import EmbeddingFunc

    config = FastEmbedConfig()

    logger.info(
        f"Creating LightRAG EmbeddingFunc: model={config.model}, "
        f"dim={config.embedding_dim}, max_token_size={config.max_token_size}"
    )

    return EmbeddingFunc(
        embedding_dim=config.embedding_dim,
        max_token_size=config.max_token_size,
        func=lightrag_embedding_func,
    )
