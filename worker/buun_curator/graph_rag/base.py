"""Abstract base classes for GraphRAG sessions."""

from abc import ABC, abstractmethod
from typing import Any

from buun_curator.graph_rag.types import (
    GraphRAGBackend,
    SearchMode,
    SearchResult,
    SessionState,
)


class GraphRAGSession(ABC):
    """
    Abstract base class for GraphRAG research sessions.

    Provides a unified interface for different GraphRAG backends.
    Each backend implements this interface with its specific behavior.

    Lifecycle
    ---------
    1. create() - Create or restore a session
    2. add() - Add content (can be called multiple times)
    3. build_graph() - Build/update the knowledge graph
    4. search() - Query the graph
    5. close() - Cleanup resources

    Note: Some backends (Graphiti) build incrementally during add(),
    making build_graph() a no-op. The interface allows for this flexibility.
    """

    # Session identification
    entry_id: str
    backend: GraphRAGBackend

    # Session state
    started: bool
    graph_name: str

    @classmethod
    @abstractmethod
    async def create(cls, entry_id: str, **kwargs: Any) -> "GraphRAGSession":
        """
        Create a new session or restore an existing one.

        Parameters
        ----------
        entry_id : str
            Unique identifier for the entry/document.
        **kwargs : Any
            Backend-specific options.

        Returns
        -------
        GraphRAGSession
            New or restored session instance.
        """

    @classmethod
    @abstractmethod
    async def reset(cls, entry_id: str) -> bool:
        """
        Reset (delete) an existing session.

        Parameters
        ----------
        entry_id : str
            Entry ID whose session should be reset.

        Returns
        -------
        bool
            True if a session was deleted, False if none existed.
        """

    @abstractmethod
    async def add_content(
        self,
        content: str,
        source_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add content to the session.

        Content is stored for graph construction. Some backends (Graphiti)
        build the graph incrementally here; others (Cognee, LightRAG)
        defer to build_graph().

        Parameters
        ----------
        content : str
            Text content to add (typically Markdown).
        source_type : str
            Content type: "text", "entry", "readme", "webpage", etc.
        metadata : dict[str, Any] | None
            Additional metadata for the content.
        """

    @abstractmethod
    async def build_graph(
        self,
        use_ontology: bool = True,
        **kwargs: Any,
    ) -> None:
        """
        Build or update the knowledge graph.

        For incremental backends (Graphiti), this may be a no-op.
        For batch backends (Cognee, LightRAG), this triggers entity
        extraction and graph construction.

        Parameters
        ----------
        use_ontology : bool
            Whether to use ontology constraints (if supported).
        **kwargs : Any
            Backend-specific options.
        """

    @abstractmethod
    async def search_graph(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Search the knowledge graph.

        Parameters
        ----------
        query : str
            Search query text.
        mode : SearchMode
            Search mode (GRAPH, SUMMARY, HYBRID, CHUNKS).
        top_k : int
            Maximum number of results.
        **kwargs : Any
            Backend-specific search options.

        Returns
        -------
        list[SearchResult]
            Search results in unified format.
        """

    @abstractmethod
    async def close(self) -> None:
        """
        Close the session and release resources.

        Does NOT delete the graph data. Use reset() to delete.
        """

    @abstractmethod
    async def delete(self) -> None:
        """
        Delete the session and all associated data.

        Removes the graph and any stored content.
        """

    def get_state(self) -> SessionState:
        """
        Get current session state for persistence/recovery.

        Returns
        -------
        SessionState
            Current state that can be used to restore the session.
        """
        return SessionState(
            entry_id=self.entry_id,
            backend=self.backend,
            graph_name=self.graph_name,
            started=self.started,
        )

    # Optional methods with default implementations

    async def get_entities(self) -> list[dict[str, Any]]:
        """
        Get all entities in the graph.

        Returns
        -------
        list[dict[str, Any]]
            List of entity dictionaries.
        """
        return []

    async def get_relationships(self) -> list[dict[str, Any]]:
        """
        Get all relationships in the graph.

        Returns
        -------
        list[dict[str, Any]]
            List of relationship dictionaries.
        """
        return []

    async def is_empty(self) -> bool:
        """
        Check if the graph is empty.

        Returns
        -------
        bool
            True if no entities exist in the graph.
        """
        entities = await self.get_entities()
        return len(entities) == 0
