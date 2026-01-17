"""
Entry-specific Graphiti session for Deep Research.

Provides session-scoped data isolation using FalkorDB's database parameter
and Graphiti's group_id, enabling per-entry knowledge graphs.

Key differences from Cognee:
- Graph is built incrementally via add_episode() (no batch cognify step)
- build_graph() is a no-op (graph already built during add_content)
- Hybrid search is the default and only mode
- Bi-temporal versioning for fact history tracking
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from buun_curator.graph_rag.base import GraphRAGSession
from buun_curator.graph_rag.types import (
    GraphRAGBackend,
    SearchMode,
    SearchResult,
)

logger = logging.getLogger(__name__)

# Track if Graphiti indices have been built per database
_graphiti_initialized: set[str] = set()


class GraphitiSession(GraphRAGSession):
    """
    Deep Research session for a specific entry using Graphiti.

    Uses FalkorDB with per-entry database isolation via graph name.
    The graph is built incrementally as content is added (no batch step).

    Examples
    --------
    >>> session = await GraphitiSession.create(entry_id)
    ... await session.add_content(entry_content)
    ... await session.add_content(github_readme, source_type="readme")
    ... # Graph is already built - build_graph() is a no-op
    ... results = await session.search_graph("What is the main topic?")
    ... await session.close()
    """

    # GraphRAGSession backend identifier
    backend = GraphRAGBackend.GRAPHITI

    def __init__(
        self,
        entry_id: str,
        graph_name: str,
        started: bool = False,
    ):
        """
        Initialize a Graphiti session.

        Use GraphitiSession.create() instead of direct instantiation.

        Parameters
        ----------
        entry_id : str
            The entry ID this session belongs to.
        graph_name : str
            The FalkorDB graph name for isolation.
        started : bool
            Whether the session has started (content has been added).
        """
        self.entry_id = entry_id
        self.graph_name = graph_name
        self.started = started
        self._graphiti: Any = None  # Lazy-initialized Graphiti instance
        self._driver: Any = None  # FalkorDriver instance

    def _get_falkordb_config(self) -> dict[str, Any]:
        """
        Get FalkorDB connection configuration from environment.

        Returns
        -------
        dict[str, Any]
            FalkorDB configuration dict.
        """
        return {
            "host": os.getenv("FALKORDB_HOST", "localhost"),
            "port": int(os.getenv("FALKORDB_PORT", "6379")),
            "username": os.getenv("FALKORDB_USERNAME") or None,
            "password": os.getenv("FALKORDB_PASSWORD") or None,
            "database": self.graph_name,
        }

    def _get_llm_config(self) -> dict[str, Any]:
        """
        Get LLM configuration from environment.

        Returns
        -------
        dict[str, Any]
            LLM configuration dict with model and API settings.
        """
        return {
            "model": os.getenv("GRAPH_RAG_LLM_MODEL") or os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("OPENAI_API_KEY"),
            "base_url": os.getenv("OPENAI_BASE_URL"),
        }

    async def _get_graphiti(self) -> Any:
        """
        Get or create the Graphiti instance.

        Lazily initializes the Graphiti client with FalkorDB backend.
        Creates indices on first use per database.

        Returns
        -------
        Graphiti
            Initialized Graphiti instance.
        """
        if self._graphiti is not None:
            return self._graphiti

        from graphiti_core import Graphiti
        from graphiti_core.driver.falkordb_driver import FalkorDriver
        from graphiti_core.llm_client.config import LLMConfig
        from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

        from buun_curator.graphiti.embedder import FastEmbedEmbedder

        config = self._get_falkordb_config()
        logger.debug(
            f"Creating FalkorDriver for {self.graph_name} at {config['host']}:{config['port']}"
        )

        # Create driver with entry-specific database
        # Note: FalkorDriver constructor schedules build_indices_and_constraints()
        # as a background task automatically. We need to wait for it to complete.
        self._driver = FalkorDriver(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database=config["database"],
        )

        # Configure LLM client for LiteLLM proxy compatibility
        # OpenAIGenericClient uses chat.completions.create which works with LiteLLM
        llm_config = self._get_llm_config()
        llm_client_config = LLMConfig(
            model=llm_config["model"],
            api_key=llm_config["api_key"],
            base_url=llm_config["base_url"],
        )
        llm_client = OpenAIGenericClient(config=llm_client_config)

        # Use FastEmbed for local embedding (no API calls)
        embedder = FastEmbedEmbedder()

        logger.debug(f"Using LLM model: {llm_config['model']}")

        # Create Graphiti instance with custom LLM and embedder
        self._graphiti = Graphiti(
            graph_driver=self._driver,
            llm_client=llm_client,
            embedder=embedder,
        )

        # Wait for the background index creation task to complete
        # FalkorDriver schedules this in __init__, we need to wait for it
        if self.graph_name not in _graphiti_initialized:
            logger.info(f"Waiting for indices to be built for graph {self.graph_name}")
            # Give the background task time to complete
            # The task was scheduled in FalkorDriver.__init__
            await asyncio.sleep(0.5)
            _graphiti_initialized.add(self.graph_name)
            logger.info(f"Indices ready for graph {self.graph_name}")

        return self._graphiti

    @classmethod
    async def create(cls, entry_id: str, **_kwargs: Any) -> "GraphitiSession":
        """
        Create a Graphiti session for an entry.

        Unlike Cognee, Graphiti doesn't have explicit dataset state to restore.
        The graph data persists in FalkorDB and is accessed by graph name.
        We check if the graph has any nodes to determine if it's "started".

        Parameters
        ----------
        entry_id : str
            The entry ID to create a session for.
        **_kwargs : Any
            Additional options (ignored for now).

        Returns
        -------
        GraphitiSession
            New session instance with started=True if graph has data.
        """
        graph_name = f"buun_curator_graphiti_{entry_id}"
        logger.debug(f"Creating GraphitiSession for entry {entry_id}")

        # Check if graph has existing data
        started = await cls._check_graph_has_data(graph_name)
        if started:
            logger.debug(f"Graph {graph_name} has existing data, marking as started")

        return cls(entry_id=entry_id, graph_name=graph_name, started=started)

    @classmethod
    async def _check_graph_has_data(cls, graph_name: str) -> bool:
        """
        Check if a graph has any data (nodes).

        Parameters
        ----------
        graph_name : str
            The FalkorDB graph name.

        Returns
        -------
        bool
            True if graph has nodes, False otherwise.
        """
        import os

        from graphiti_core.driver.falkordb_driver import FalkorDriver

        try:
            driver = FalkorDriver(
                host=os.getenv("FALKORDB_HOST", "localhost"),
                port=int(os.getenv("FALKORDB_PORT", "6379")),
                username=os.getenv("FALKORDB_USERNAME") or None,
                password=os.getenv("FALKORDB_PASSWORD") or None,
                database=graph_name,
            )

            # Check if any nodes exist
            result = await driver.execute_query("MATCH (n) RETURN count(n) as cnt LIMIT 1")
            logger.debug(f"_check_graph_has_data query result for {graph_name}: {result}")
            await driver.close()

            # FalkorDriver.execute_query returns (rows, columns, stats) tuple
            # rows is a list of dicts like [{'cnt': 16}]
            if result and len(result) > 0:
                rows = result[0]  # First element is the rows list
                logger.debug(f"Rows type: {type(rows)}, value: {rows}")
                if rows and len(rows) > 0:
                    record = rows[0]  # First row
                    logger.debug(f"Record type: {type(record)}, value: {record}")
                    if isinstance(record, dict):
                        count = record.get("cnt", 0)
                    else:
                        count = getattr(record, "cnt", 0)
                    logger.debug(f"Node count for {graph_name}: {count}")
                    return int(count) > 0
            logger.debug(f"No result rows for {graph_name}")
            return False

        except Exception as e:
            logger.warning(f"Could not check graph data for {graph_name}: {e}")
            return False

    @classmethod
    async def reset(cls, entry_id: str) -> bool:
        """
        Reset (delete) an existing session for an entry.

        Removes all nodes and relationships from the FalkorDB graph.

        Parameters
        ----------
        entry_id : str
            The entry ID whose session should be reset.

        Returns
        -------
        bool
            True if graph was cleared, False if it didn't exist.
        """
        graph_name = f"buun_curator_graphiti_{entry_id}"
        logger.info(f"Resetting GraphitiSession for entry {entry_id}")

        from graphiti_core.driver.falkordb_driver import FalkorDriver

        config = {
            "host": os.getenv("FALKORDB_HOST", "localhost"),
            "port": int(os.getenv("FALKORDB_PORT", "6379")),
            "username": os.getenv("FALKORDB_USERNAME") or None,
            "password": os.getenv("FALKORDB_PASSWORD") or None,
            "database": graph_name,
        }

        try:
            driver = FalkorDriver(
                host=config["host"],
                port=config["port"],
                username=config["username"],
                password=config["password"],
                database=config["database"],
            )

            # Delete all nodes and relationships
            # FalkorDB uses Cypher-like query language
            query = "MATCH (n) DETACH DELETE n"
            await driver.execute_query(query)
            await driver.close()

            # Remove from initialized set so indices are rebuilt on next use
            _graphiti_initialized.discard(graph_name)

            logger.info(f"GraphitiSession for entry {entry_id} reset successfully")
            return True

        except Exception as e:
            logger.warning(f"Failed to reset GraphitiSession for {entry_id}: {e}")
            return False

    async def add_content(
        self,
        content: str,
        source_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add content to the session and build graph incrementally.

        Unlike Cognee, Graphiti builds the graph as episodes are added.
        No separate build_graph() step is needed.

        Parameters
        ----------
        content : str
            Text content to add (typically Markdown).
        source_type : str
            Content type: "text", "entry", "readme", "webpage", etc.
        metadata : dict[str, Any] | None
            Additional metadata for the episode.
        """
        from graphiti_core.nodes import EpisodeType

        graphiti = await self._get_graphiti()

        # Map source_type to Graphiti's EpisodeType
        episode_type = EpisodeType.text
        if source_type == "json":
            episode_type = EpisodeType.json

        # Generate unique episode name
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        episode_name = f"{self.entry_id}_{source_type}_{timestamp}"

        # Build source description from metadata
        source_description = source_type
        if metadata:
            if "title" in metadata:
                source_description = f"{source_type}: {metadata['title']}"
            elif "url" in metadata:
                source_description = f"{source_type}: {metadata['url']}"

        logger.info(f"Adding episode to {self.graph_name}: {episode_name} ({len(content)} chars)")

        # Add episode - graph is built incrementally
        # IMPORTANT: group_id must match the database name (graph_name) because
        # Graphiti clones the driver with group_id as the new database name.
        # If group_id differs from the driver's _database, it creates a new connection
        # to a database named after group_id, which may not match FalkorDB's ACL pattern.
        await graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source=episode_type,
            source_description=source_description,
            reference_time=datetime.now(UTC),
            group_id=self.graph_name,  # Must match driver's database name for ACL
        )

        self.started = True
        logger.info(f"Episode {episode_name} added successfully")

    async def build_graph(
        self,
        use_ontology: bool = True,
        **_kwargs: Any,
    ) -> None:
        """
        Build the knowledge graph (no-op for Graphiti).

        Graphiti builds the graph incrementally during add_content(),
        so this method does nothing. It exists for interface compatibility.

        Note: This method always succeeds because Graphiti's graph is already
        built during add_episode(). The started check is skipped here since
        the graph state is maintained by FalkorDB, not in-memory.

        Parameters
        ----------
        use_ontology : bool
            Ignored - Graphiti doesn't use external ontology files.
        **_kwargs : Any
            Additional options (ignored).
        """
        # No-op: Graphiti builds graph incrementally during add_episode()
        # Mark as started since if build_graph is called, content was likely added
        self.started = True
        _ = use_ontology
        logger.debug(
            f"build_graph() called for {self.graph_name} - no-op (Graphiti builds incrementally)"
        )

    async def search_graph(
        self,
        query: str,
        mode: SearchMode = SearchMode.HYBRID,  # noqa: ARG002
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[SearchResult]:
        """
        Search the knowledge graph.

        Graphiti uses hybrid search (semantic + BM25 + graph) by default.
        The mode parameter is accepted for interface compatibility but
        all modes map to hybrid search.

        Parameters
        ----------
        query : str
            Search query text.
        mode : SearchMode
            Search mode (accepted but all map to hybrid).
        top_k : int
            Maximum number of results.
        **kwargs : Any
            Additional options (center_node_uuid for reranking).

        Returns
        -------
        list[SearchResult]
            Search results in unified format.
        """
        logger.debug(f"search_graph called: started={self.started}, graph={self.graph_name}")
        if not self.started:
            logger.warning(f"Search on empty session {self.graph_name} (started=False)")
            return []

        graphiti = await self._get_graphiti()

        logger.info(f"Searching {self.graph_name}: query={query!r}, top_k={top_k}")

        # Graphiti's search() does hybrid search by default
        # Optional: center_node_uuid for node-distance reranking
        center_node_uuid = kwargs.get("center_node_uuid")

        # Pass group_ids to search within this session's graph partition
        logger.debug(f"Calling graphiti.search with group_ids=[{self.graph_name}]")
        if center_node_uuid:
            raw_results = await graphiti.search(
                query=query,
                center_node_uuid=center_node_uuid,
                group_ids=[self.graph_name],
                num_results=top_k,
            )
        else:
            raw_results = await graphiti.search(
                query=query,
                group_ids=[self.graph_name],
                num_results=top_k,
            )

        logger.debug(f"Raw results from graphiti.search: {len(raw_results)} items")
        if raw_results:
            logger.debug(f"First raw result type: {type(raw_results[0])}")

        # Convert to unified SearchResult format
        results = []
        for i, result in enumerate(raw_results[:top_k]):
            results.append(self._to_search_result(result, i))

        logger.info(f"Search returned {len(results)} results")
        return results

    def _to_search_result(self, raw: Any, index: int) -> SearchResult:
        """
        Convert Graphiti search result to unified SearchResult.

        Parameters
        ----------
        raw : Any
            Raw Graphiti search result (EntityEdge, Node, etc.).
        index : int
            Result index for scoring.

        Returns
        -------
        SearchResult
            Unified search result.
        """
        # Graphiti returns various types (EntityEdge, Node, etc.)
        if hasattr(raw, "fact"):
            # EntityEdge - relationship with fact text
            return SearchResult(
                id=str(getattr(raw, "uuid", f"edge_{index}")),
                content=str(raw.fact),
                score=1.0 / (index + 1),  # RRF-style scoring
                metadata={
                    "source_node_uuid": getattr(raw, "source_node_uuid", None),
                    "target_node_uuid": getattr(raw, "target_node_uuid", None),
                    "relationship_type": getattr(raw, "relationship_type", None),
                    "valid_at": str(getattr(raw, "valid_at", None)),
                    "invalid_at": str(getattr(raw, "invalid_at", None)),
                },
                source_type="relationship",
                raw=raw.model_dump() if hasattr(raw, "model_dump") else None,
            )
        elif hasattr(raw, "name"):
            # Node - entity
            return SearchResult(
                id=str(getattr(raw, "uuid", f"node_{index}")),
                content=str(raw.name),
                score=1.0 / (index + 1),
                metadata={
                    "labels": getattr(raw, "labels", []),
                    "created_at": str(getattr(raw, "created_at", None)),
                },
                source_type="entity",
                raw=raw.model_dump() if hasattr(raw, "model_dump") else None,
            )
        else:
            # Unknown type - convert to string
            return SearchResult(
                id=f"result_{index}",
                content=str(raw),
                score=1.0 / (index + 1),
                source_type="unknown",
            )

    async def close(self) -> None:
        """
        Close the session and release resources.

        Does NOT delete the graph data. Use reset() to delete data.
        """
        if self._graphiti is not None:
            logger.debug(f"Closing GraphitiSession for {self.graph_name}")
            await self._graphiti.close()
            self._graphiti = None
            self._driver = None

    async def delete(self) -> None:
        """
        Delete the session and all associated data.

        Clears the FalkorDB graph and closes the connection.
        """
        await self.close()
        await self.reset(self.entry_id)
        self.started = False

    # =========================================================================
    # Optional GraphRAGSession methods
    # =========================================================================

    async def get_entities(self) -> list[dict[str, Any]]:
        """
        Get all entities (nodes) in the graph.

        Returns
        -------
        list[dict[str, Any]]
            List of entity dictionaries.
        """
        if not self.started:
            return []

        # Ensure graphiti is initialized (initializes self._driver)
        await self._get_graphiti()

        # Query all nodes
        query = "MATCH (n:Entity) RETURN n"
        try:
            result = await self._driver.execute_query(query)
            nodes = []
            for record in result:
                node = record.get("n", {})
                nodes.append(
                    {
                        "uuid": node.get("uuid"),
                        "name": node.get("name"),
                        "labels": node.get("labels", []),
                    }
                )
            return nodes
        except Exception as e:
            logger.warning(f"Failed to get entities: {e}")
            return []

    async def get_relationships(self) -> list[dict[str, Any]]:
        """
        Get all relationships (edges) in the graph.

        Returns
        -------
        list[dict[str, Any]]
            List of relationship dictionaries.
        """
        if not self.started:
            return []

        try:
            query = "MATCH (a)-[r:RELATES_TO]->(b) RETURN r, a.uuid as source, b.uuid as target"
            result = await self._driver.execute_query(query)
            edges = []
            for record in result:
                rel = record.get("r", {})
                edges.append(
                    {
                        "source_uuid": record.get("source"),
                        "target_uuid": record.get("target"),
                        "fact": rel.get("fact"),
                        "relationship_type": rel.get("relationship_type"),
                    }
                )
            return edges
        except Exception as e:
            logger.warning(f"Failed to get relationships: {e}")
            return []
