"""
FastEmbed-based embedder for Graphiti.

Provides a local embedding solution using FastEmbed, eliminating
the need for external API calls for embedding generation.
"""

import asyncio
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass, field

from graphiti_core.embedder.client import EmbedderClient

logger = logging.getLogger(__name__)

# Default model and dimensions
DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"
DEFAULT_DIMENSIONS = 768


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
        default_factory=lambda: (
            int(val) if (val := os.getenv("EMBEDDING_THREADS")) else None
        )
    )


class FastEmbedEmbedder(EmbedderClient):
    """
    Embedder using FastEmbed for local embedding generation.

    Uses ONNX Runtime for efficient CPU-based embedding without
    requiring GPU or large PyTorch dependencies.
    """

    def __init__(self, config: FastEmbedConfig | None = None):
        """
        Initialize the FastEmbed embedder.

        Parameters
        ----------
        config : FastEmbedConfig | None
            Configuration for the embedder. Uses defaults from
            environment variables if not provided.
        """
        self.config = config or FastEmbedConfig()
        self._model = None
        logger.info(
            f"FastEmbedEmbedder initialized with model={self.config.model}, "
            f"dim={self.config.embedding_dim}"
        )

    def _get_model(self):
        """
        Lazily initialize the FastEmbed model.

        Returns
        -------
        TextEmbedding
            Initialized FastEmbed model.
        """
        if self._model is None:
            from fastembed import TextEmbedding

            logger.debug(f"Loading FastEmbed model: {self.config.model}")
            kwargs: dict = {"model_name": self.config.model}
            if self.config.threads is not None:
                kwargs["threads"] = self.config.threads
                logger.info(f"FastEmbed using {self.config.threads} threads")
            self._model = TextEmbedding(**kwargs)
            logger.debug(f"FastEmbed model loaded: {self.config.model}")
        return self._model

    async def create(
        self,
        input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]],
    ) -> list[float]:
        """
        Create embedding for input text.

        Parameters
        ----------
        input_data : str | list[str] | Iterable[int] | Iterable[Iterable[int]]
            Text or list of texts to embed. Token IDs are not supported.

        Returns
        -------
        list[float]
            Embedding vector for the first input text.
        """
        # FastEmbed only supports text input, not token IDs
        texts: list[str]
        if isinstance(input_data, str):
            texts = [input_data]
        elif isinstance(input_data, list) and all(isinstance(t, str) for t in input_data):
            texts = input_data  # type: ignore[assignment]
        else:
            raise ValueError("FastEmbedEmbedder only supports text input, not token IDs")

        # Run embedding in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self._get_model().embed(texts)),
        )

        # Return first embedding as list of floats
        return embeddings[0].tolist()

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """
        Create embeddings for multiple texts in batch.

        Parameters
        ----------
        input_data_list : list[str]
            List of texts to embed.

        Returns
        -------
        list[list[float]]
            List of embedding vectors.
        """
        if not input_data_list:
            return []

        # Run embedding in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(
            None,
            lambda: list(self._get_model().embed(input_data_list)),
        )

        return [e.tolist() for e in embeddings]
