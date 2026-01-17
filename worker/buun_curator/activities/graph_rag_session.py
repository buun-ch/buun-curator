"""
GraphRAG Session Activities (Graphiti).

Temporal activities for managing entry-specific GraphRAG sessions using Graphiti.
"""

from temporalio import activity

from buun_curator.graph_rag.types import SearchMode
from buun_curator.graphiti.session import GraphitiSession
from buun_curator.logging import get_logger
from buun_curator.models import (
    AddToGraphRAGSessionInput,
    AddToGraphRAGSessionOutput,
    BuildGraphRAGGraphInput,
    BuildGraphRAGGraphOutput,
    CloseGraphRAGSessionInput,
    CloseGraphRAGSessionOutput,
    ResetGraphRAGSessionInput,
    ResetGraphRAGSessionOutput,
    SearchGraphRAGSessionInput,
    SearchGraphRAGSessionOutput,
)

logger = get_logger(__name__)


def _search_mode_from_str(mode: str) -> SearchMode:
    """
    Convert search mode string to SearchMode enum.

    Parameters
    ----------
    mode : str
        Search mode string.

    Returns
    -------
    SearchMode
        Corresponding SearchMode enum value.
    """
    mode_map = {
        # Current enum values
        "naive": SearchMode.NAIVE,
        "local": SearchMode.LOCAL,
        "global": SearchMode.GLOBAL,
        "hybrid": SearchMode.HYBRID,
        "mix": SearchMode.MIX,
        # Legacy aliases
        "graph": SearchMode.LOCAL,  # entity relationships
        "summary": SearchMode.GLOBAL,  # summaries
        "chunks": SearchMode.NAIVE,  # raw chunk search
    }
    return mode_map.get(mode.lower(), SearchMode.HYBRID)


@activity.defn
async def add_to_graph_rag_session(
    input: AddToGraphRAGSessionInput,
) -> AddToGraphRAGSessionOutput:
    """
    Add content to an entry-specific GraphRAG session.

    Creates the session if it doesn't exist. Graphiti builds the graph
    incrementally as content is added.

    Parameters
    ----------
    input : AddToGraphRAGSessionInput
        Entry ID, content, source type, and optional metadata.

    Returns
    -------
    AddToGraphRAGSessionOutput
        Success status and graph name.
    """
    logger.info(
        "Adding content to Graphiti session",
        entry_id=input.entry_id,
        source_type=input.source_type,
        chars=len(input.content),
    )

    try:
        session = await GraphitiSession.create(input.entry_id)

        await session.add_content(
            content=input.content,
            source_type=input.source_type,
            metadata=input.metadata,
        )

        logger.info(
            "Successfully added content to Graphiti session", graph_name=session.graph_name
        )
        return AddToGraphRAGSessionOutput(
            success=True,
            graph_name=session.graph_name,
        )
    except Exception as e:
        logger.error(
            f"Failed to add content to Graphiti session: {e}", entry_id=input.entry_id
        )
        return AddToGraphRAGSessionOutput(
            success=False,
            graph_name="",
            error=str(e),
        )


@activity.defn
async def build_graph_rag_graph(
    input: BuildGraphRAGGraphInput,
) -> BuildGraphRAGGraphOutput:
    """
    Build the knowledge graph for an entry's session.

    For Graphiti, this is a no-op since the graph is built incrementally
    during add_content(). This activity exists for interface compatibility.

    Parameters
    ----------
    input : BuildGraphRAGGraphInput
        Entry ID.

    Returns
    -------
    BuildGraphRAGGraphOutput
        Success status and graph name.
    """
    logger.info("Building Graphiti graph", entry_id=input.entry_id)

    try:
        session = await GraphitiSession.create(input.entry_id)

        # Graphiti builds graph incrementally, so this is a no-op
        await session.build_graph()

        logger.info("Successfully built Graphiti graph", graph_name=session.graph_name)
        return BuildGraphRAGGraphOutput(
            success=True,
            graph_name=session.graph_name,
        )
    except Exception as e:
        logger.error(f"Failed to build Graphiti graph: {e}", entry_id=input.entry_id)
        return BuildGraphRAGGraphOutput(
            success=False,
            graph_name="",
            error=str(e),
        )


@activity.defn
async def search_graph_rag_session(
    input: SearchGraphRAGSessionInput,
) -> SearchGraphRAGSessionOutput:
    """
    Search an entry's knowledge graph.

    Parameters
    ----------
    input : SearchGraphRAGSessionInput
        Entry ID, query, search mode, and top_k.

    Returns
    -------
    SearchGraphRAGSessionOutput
        Success status and search results.
    """
    logger.info(
        "Searching Graphiti session",
        entry_id=input.entry_id,
        query=input.query,
        mode=input.search_mode,
    )

    try:
        session = await GraphitiSession.create(input.entry_id)

        search_mode = _search_mode_from_str(input.search_mode)
        results = await session.search_graph(
            query=input.query,
            mode=search_mode,
            top_k=input.top_k,
        )

        # Convert SearchResult objects to dicts
        results_dicts = [result.model_dump() for result in results]

        logger.info("Search returned results from Graphiti session", count=len(results_dicts))
        return SearchGraphRAGSessionOutput(
            success=True,
            results=results_dicts,
        )
    except Exception as e:
        logger.error(f"Failed to search Graphiti session: {e}", entry_id=input.entry_id)
        return SearchGraphRAGSessionOutput(
            success=False,
            error=str(e),
        )


@activity.defn
async def reset_graph_rag_session(
    input: ResetGraphRAGSessionInput,
) -> ResetGraphRAGSessionOutput:
    """
    Reset an entry's session by deleting existing data.

    Parameters
    ----------
    input : ResetGraphRAGSessionInput
        Entry ID.

    Returns
    -------
    ResetGraphRAGSessionOutput
        Success status and whether a session was deleted.
    """
    logger.info("Resetting Graphiti session", entry_id=input.entry_id)

    try:
        deleted = await GraphitiSession.reset(input.entry_id)

        if deleted:
            logger.info("Successfully reset Graphiti session", entry_id=input.entry_id)
        else:
            logger.debug("No existing Graphiti session", entry_id=input.entry_id)

        return ResetGraphRAGSessionOutput(
            success=True,
            deleted=deleted,
        )
    except Exception as e:
        logger.error(f"Failed to reset Graphiti session: {e}", entry_id=input.entry_id)
        return ResetGraphRAGSessionOutput(
            success=False,
            deleted=False,
            error=str(e),
        )


@activity.defn
async def close_graph_rag_session(
    input: CloseGraphRAGSessionInput,
) -> CloseGraphRAGSessionOutput:
    """
    Close an entry's session and release resources.

    Does NOT delete session data. Use reset_graph_rag_session for that.

    Parameters
    ----------
    input : CloseGraphRAGSessionInput
        Entry ID.

    Returns
    -------
    CloseGraphRAGSessionOutput
        Success status.
    """
    logger.info("Closing Graphiti session", entry_id=input.entry_id)

    try:
        session = await GraphitiSession.create(input.entry_id)
        await session.close()

        logger.info("Successfully closed Graphiti session", entry_id=input.entry_id)
        return CloseGraphRAGSessionOutput(
            success=True,
        )
    except Exception as e:
        logger.error(f"Failed to close Graphiti session: {e}", entry_id=input.entry_id)
        return CloseGraphRAGSessionOutput(
            success=False,
            error=str(e),
        )
