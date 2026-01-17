"""
Global knowledge graph using LightRAG with Memgraph storage.

Each operation creates a new LightRAG instance with a unique trace_id,
allowing proper Langfuse tracing for parallel workflow executions.
"""

import logging
import os
import uuid
from functools import partial
from typing import Any, Literal

logger = logging.getLogger(__name__)

# LightRAG query mode type
LightRAGQueryMode = Literal["local", "global", "hybrid", "naive", "mix", "bypass"]

# Default workspace name for global graph
GLOBAL_GRAPH_WORKSPACE = "buun_curator"


def _get_memgraph_config() -> dict[str, str]:
    """
    Get Memgraph connection configuration from environment.

    Builds URI from MEMGRAPH_HOST and MEMGRAPH_PORT environment variables.

    Returns
    -------
    dict[str, str]
        Memgraph configuration dict with 'uri', 'username', 'password', 'database'.
    """
    host = os.getenv("MEMGRAPH_HOST", "localhost")
    port = os.getenv("MEMGRAPH_PORT", "7687")
    return {
        "uri": f"bolt://{host}:{port}",
        "username": os.getenv("MEMGRAPH_USERNAME", ""),
        "password": os.getenv("MEMGRAPH_PASSWORD", ""),
        # Empty string if not set (Memgraph free version has no database concept)
        "database": os.getenv("MEMGRAPH_DATABASE", ""),
    }


def _get_lightrag_config() -> dict[str, Any]:
    """
    Get LightRAG configuration from environment.

    Returns
    -------
    dict[str, Any]
        LightRAG configuration dict.
    """
    return {
        "working_dir": os.getenv("LIGHTRAG_WORKING_DIR", "/tmp/lightrag"),
        "query_mode": os.getenv("LIGHTRAG_QUERY_MODE", "hybrid"),
    }


def _setup_memgraph_env() -> None:
    """Set Memgraph environment variables for LightRAG's MemgraphStorage."""
    memgraph_config = _get_memgraph_config()
    os.environ["MEMGRAPH_URI"] = memgraph_config["uri"]
    if memgraph_config["username"]:
        os.environ["MEMGRAPH_USERNAME"] = memgraph_config["username"]
    if memgraph_config["password"]:
        os.environ["MEMGRAPH_PASSWORD"] = memgraph_config["password"]
    if memgraph_config["database"]:
        os.environ["MEMGRAPH_DATABASE"] = memgraph_config["database"]


async def _create_lightrag_instance(trace_id: str | None = None) -> Any:
    """
    Create a new LightRAG instance.

    Parameters
    ----------
    trace_id : str | None
        Langfuse trace ID for grouping LLM calls within this instance.

    Returns
    -------
    LightRAG
        Initialized LightRAG instance.
    """
    from lightrag import LightRAG
    from lightrag.kg.shared_storage import initialize_pipeline_status

    from buun_curator.lightrag.embedder import get_lightrag_embedding_func
    from buun_curator.lightrag.llm import lightrag_llm_func

    config = _get_lightrag_config()
    memgraph_config = _get_memgraph_config()

    logger.info(
        f"Creating LightRAG instance: "
        f"working_dir={config['working_dir']}, "
        f"memgraph_uri={memgraph_config['uri']}, "
        f"trace_id={trace_id}"
    )

    # Set Memgraph environment variables
    _setup_memgraph_env()

    # Create LLM function with trace_id bound
    llm_func = (
        partial(lightrag_llm_func, trace_id=trace_id) if trace_id else lightrag_llm_func
    )

    # Create LightRAG instance with Memgraph storage
    rag = LightRAG(
        working_dir=config["working_dir"],
        llm_model_func=llm_func,
        embedding_func=get_lightrag_embedding_func(),
        graph_storage="MemgraphStorage",
    )

    # Initialize storages (required before use)
    await rag.initialize_storages()

    # Initialize pipeline status (required for ainsert to work)
    await initialize_pipeline_status()

    logger.info("LightRAG instance created successfully")
    return rag


def _build_full_content(
    content: str,
    entry_id: str,
    source_type: str,
    title: str | None,
    url: str | None,
) -> str:
    """
    Build full content with metadata prepended.

    Parameters
    ----------
    content : str
        Text content to add.
    entry_id : str
        The entry ID for tracking.
    source_type : str
        Content type.
    title : str | None
        Optional title.
    url : str | None
        Optional URL.

    Returns
    -------
    str
        Content with metadata prepended.
    """
    metadata_lines = []
    if title:
        metadata_lines.append(f"Title: {title}")
    if url:
        metadata_lines.append(f"URL: {url}")
    if entry_id:
        metadata_lines.append(f"Entry ID: {entry_id}")
    if source_type:
        metadata_lines.append(f"Source Type: {source_type}")

    return "\n".join(metadata_lines) + "\n\n" + content if metadata_lines else content


async def add_content_to_global_graph(
    content: str,
    entry_id: str,
    source_type: str = "entry",
    title: str | None = None,
    url: str | None = None,
) -> bool:
    """
    Add content to the global knowledge graph.

    Creates a new LightRAG instance with a unique trace_id for this operation.

    Parameters
    ----------
    content : str
        Text content to add (typically Markdown).
    entry_id : str
        The entry ID for tracking.
    source_type : str
        Content type: "entry", "readme", "webpage", etc.
    title : str | None
        Optional title for context.
    url : str | None
        Optional URL for context.

    Returns
    -------
    bool
        True if content was added successfully.
    """
    trace_id = uuid.uuid4().hex[:32]
    rag = await _create_lightrag_instance(trace_id=trace_id)

    full_content = _build_full_content(content, entry_id, source_type, title, url)

    logger.info(
        f"Adding content to LightRAG: "
        f"entry_id={entry_id}, source_type={source_type}, "
        f"chars={len(content)}, trace_id={trace_id}"
    )

    try:
        await rag.ainsert(full_content)
        logger.info(f"Content added successfully: entry_id={entry_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to add content to LightRAG: {e}")
        return False


async def add_contents_bulk_to_global_graph(
    contents: list[dict[str, Any]],
) -> tuple[int, int]:
    """
    Add multiple contents to the global knowledge graph.

    Creates a single LightRAG instance with a shared trace_id for all contents,
    grouping all LLM calls under one Langfuse trace. Uses LightRAG's native
    batch insert for better performance.

    Parameters
    ----------
    contents : list[dict[str, Any]]
        List of content dicts with keys: content, entry_id, source_type, title, url.

    Returns
    -------
    tuple[int, int]
        (success_count, failed_count)
    """
    if not contents:
        return 0, 0

    # Generate a single trace_id for the entire bulk operation
    trace_id = uuid.uuid4().hex[:32]
    rag = await _create_lightrag_instance(trace_id=trace_id)

    logger.info(
        f"Bulk adding {len(contents)} contents to LightRAG, trace_id={trace_id}"
    )

    # Build all contents, IDs, and file paths for batch insert
    full_contents: list[str] = []
    entry_ids: list[str] = []
    file_paths: list[str] = []

    for item in contents:
        entry_id = item.get("entry_id", "")
        title = item.get("title") or "untitled"
        full_content = _build_full_content(
            content=item.get("content", ""),
            entry_id=entry_id,
            source_type=item.get("source_type", "entry"),
            title=title,
            url=item.get("url"),
        )
        full_contents.append(full_content)
        entry_ids.append(entry_id)
        # Use title as file_path for better log readability
        file_paths.append(f"{entry_id}:{title[:50]}")

    try:
        # Use LightRAG's native batch insert with file_paths for logging
        await rag.ainsert(full_contents, ids=entry_ids, file_paths=file_paths)
        success_count = len(contents)
        failed_count = 0
        logger.info(f"Batch insert successful: {success_count} contents added")
    except Exception as e:
        logger.error(f"Batch insert failed: {e}")
        success_count = 0
        failed_count = len(contents)

    logger.info(
        f"Bulk add complete: success={success_count}, failed={failed_count}, "
        f"trace_id={trace_id}"
    )
    return success_count, failed_count


async def search_global_graph(
    query: str,
    mode: LightRAGQueryMode = "hybrid",
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """
    Search the global knowledge graph.

    Parameters
    ----------
    query : str
        Search query text.
    mode : LightRAGQueryMode
        Search mode: naive, local, global, hybrid, mix, bypass.
    top_k : int
        Maximum number of results (used for context, LightRAG returns text).

    Returns
    -------
    list[dict[str, Any]]
        Search results with content and metadata.
    """
    from lightrag import QueryParam

    # Create instance without trace_id for search (less important to trace)
    rag = await _create_lightrag_instance(trace_id=None)

    logger.info(f"Searching LightRAG: query={query!r}, mode={mode}")

    try:
        # LightRAG returns a string response, not structured results
        result = await rag.aquery(
            query,
            param=QueryParam(mode=mode, top_k=top_k),
        )

        logger.info(f"Search returned {len(result)} chars")

        # Wrap in list format for consistency with other backends
        return [
            {
                "id": "lightrag_response",
                "content": result,
                "score": 1.0,
                "mode": mode,
                "source_type": "lightrag",
            }
        ]

    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []


async def reset_global_lightrag() -> tuple[bool, int]:
    """
    Reset the global LightRAG graph (clear all data).

    Creates a temporary instance to access and clear the graph storage.

    Returns
    -------
    tuple[bool, int]
        (success, deleted_count) - deleted_count is approximate.
    """
    logger.info("Resetting LightRAG graph")

    try:
        rag = await _create_lightrag_instance(trace_id=None)

        # Get the graph storage and clear it
        if hasattr(rag, "graph_storage_cls"):
            storage = rag.graph_storage_cls
            if hasattr(storage, "drop"):
                await storage.drop()
                logger.info("Graph storage dropped")

        logger.info("LightRAG reset successfully")
        return True, 0  # Memgraph doesn't easily return count

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to reset LightRAG: {error_msg}")
        raise RuntimeError(f"Failed to reset LightRAG: {error_msg}") from e
