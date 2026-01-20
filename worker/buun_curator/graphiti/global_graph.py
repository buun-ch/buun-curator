"""
Global Graphiti graph for knowledge accumulation.

Provides a singleton Graphiti client that writes to a shared 'buun_curator' graph,
unlike GraphitiSession which creates per-entry isolated graphs.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

# Global Graphiti client singleton
_global_graphiti: Any = None
_global_driver: Any = None
_graphiti_initialized: bool = False

# Graph name for the global knowledge graph
GLOBAL_GRAPH_NAME = "buun_curator"


def _get_falkordb_config() -> dict[str, Any]:
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
        "database": GLOBAL_GRAPH_NAME,
    }


def _get_llm_config() -> dict[str, Any]:
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


async def get_global_graphiti() -> Any:
    """
    Get or create the global Graphiti client.

    Lazily initializes the singleton Graphiti client with FalkorDB backend.
    Creates indices on first use.

    Returns
    -------
    Graphiti
        Initialized global Graphiti instance.
    """
    global _global_graphiti, _global_driver, _graphiti_initialized

    if _global_graphiti is not None:
        return _global_graphiti

    from graphiti_core import Graphiti
    from graphiti_core.driver.falkordb_driver import FalkorDriver
    from graphiti_core.llm_client.config import LLMConfig
    from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient

    from buun_curator.graphiti.embedder import FastEmbedEmbedder

    config = _get_falkordb_config()
    logger.info(
        f"Creating global FalkorDriver for {GLOBAL_GRAPH_NAME} at {config['host']}:{config['port']}"
    )

    # Create driver with global database
    _global_driver = FalkorDriver(
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        database=config["database"],
    )

    # Configure LLM client for LiteLLM proxy compatibility
    llm_config = _get_llm_config()
    llm_client_config = LLMConfig(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["base_url"],
    )
    llm_client = OpenAIGenericClient(config=llm_client_config)

    # Use FastEmbed for local embedding (no API calls)
    embedder = FastEmbedEmbedder()

    logger.debug(f"Using LLM model: {llm_config['model']}")

    # Create Graphiti instance
    _global_graphiti = Graphiti(
        graph_driver=_global_driver,
        llm_client=llm_client,
        embedder=embedder,
    )

    # Wait for background index creation
    if not _graphiti_initialized:
        logger.info(f"Waiting for indices to be built for global graph {GLOBAL_GRAPH_NAME}")
        await asyncio.sleep(0.5)
        _graphiti_initialized = True
        logger.info(f"Global graph {GLOBAL_GRAPH_NAME} indices ready")

    return _global_graphiti


async def add_episode_to_global_graph(
    content: str,
    entry_id: str,
    source_type: str = "entry",
    title: str | None = None,
    url: str | None = None,
) -> bool:
    """
    Add an episode to the global knowledge graph.

    Parameters
    ----------
    content : str
        Text content to add (typically filtered_content).
    entry_id : str
        Entry ID for reference.
    source_type : str
        Content type: "entry", "readme", etc.
    title : str | None
        Entry title for source description.
    url : str | None
        Entry URL for source description.

    Returns
    -------
    bool
        True if episode was added successfully.
    """
    from graphiti_core.nodes import EpisodeType

    graphiti = await get_global_graphiti()

    # Generate unique episode name
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    episode_name = f"{source_type}_{entry_id}_{timestamp}"

    # Build source description
    source_description = source_type
    if title:
        source_description = f"{source_type}: {title}"
    elif url:
        source_description = f"{source_type}: {url}"

    logger.info(f"Adding episode to global graph: {episode_name} ({len(content)} chars)")

    try:
        await graphiti.add_episode(
            name=episode_name,
            episode_body=content,
            source=EpisodeType.text,
            source_description=source_description,
            reference_time=datetime.now(UTC),
            group_id=GLOBAL_GRAPH_NAME,
        )
        logger.info(f"Episode {episode_name} added to global graph")
        return True
    except Exception as e:
        logger.error(f"Failed to add episode to global graph: {e}")
        return False


async def add_episodes_bulk_to_global_graph(
    episodes: list[dict],
) -> tuple[int, int]:
    """
    Add multiple episodes to the global knowledge graph in bulk.

    Uses Graphiti's add_episode_bulk for efficient batch processing.

    Parameters
    ----------
    episodes : list[dict]
        List of episode dicts with keys:
        - content: str (required)
        - entry_id: str (required)
        - source_type: str (default: "entry")
        - title: str | None
        - url: str | None

    Returns
    -------
    tuple[int, int]
        (success_count, failed_count)
    """
    from graphiti_core.nodes import EpisodeType
    from graphiti_core.utils.bulk_utils import RawEpisode

    if not episodes:
        return (0, 0)

    graphiti = await get_global_graphiti()

    # Convert to RawEpisode objects
    raw_episodes: list[RawEpisode] = []
    for ep in episodes:
        entry_id = ep.get("entry_id", "")
        content = ep.get("content", "")
        source_type = ep.get("source_type", "entry")
        title = ep.get("title")
        url = ep.get("url")

        if not content:
            continue

        # Generate unique episode name
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        episode_name = f"{source_type}_{entry_id}_{timestamp}"

        # Build source description
        source_description = source_type
        if title:
            source_description = f"{source_type}: {title}"
        elif url:
            source_description = f"{source_type}: {url}"

        raw_episodes.append(
            RawEpisode(
                name=episode_name,
                content=content,
                source_description=source_description,
                source=EpisodeType.text,
                reference_time=datetime.now(UTC),
            )
        )

    if not raw_episodes:
        return (0, 0)

    logger.info(f"Adding {len(raw_episodes)} episodes to global graph in bulk")

    try:
        await graphiti.add_episode_bulk(
            bulk_episodes=raw_episodes,
            group_id=GLOBAL_GRAPH_NAME,
        )
        logger.info(f"Successfully added {len(raw_episodes)} episodes to global graph")
        return (len(raw_episodes), 0)
    except Exception as e:
        logger.error(f"Failed to add episodes in bulk to global graph: {e}")
        return (0, len(raw_episodes))


async def close_global_graphiti() -> None:
    """Close the global Graphiti client and release resources."""
    global _global_graphiti, _global_driver

    if _global_graphiti is not None:
        logger.debug("Closing global Graphiti client")
        await _global_graphiti.close()
        _global_graphiti = None
        _global_driver = None


async def reset_global_graph() -> tuple[bool, int]:
    """
    Reset (delete) the global knowledge graph.

    Removes all nodes and relationships from the FalkorDB graph.
    Also resets the singleton state so indices are rebuilt on next use.

    Returns
    -------
    tuple[bool, int]
        (success, deleted_count) where deleted_count is the number of nodes deleted.
    """
    global _global_graphiti, _global_driver, _graphiti_initialized

    logger.info(f"Resetting global graph: {GLOBAL_GRAPH_NAME}")

    from graphiti_core.driver.falkordb_driver import FalkorDriver

    config = _get_falkordb_config()

    try:
        driver = FalkorDriver(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database=config["database"],
        )

        # Count nodes before deletion
        count_query = "MATCH (n) RETURN count(n) as cnt"
        result = await driver.execute_query(count_query)
        deleted_count = 0
        if result and len(result) > 0:
            row = result[0]
            if isinstance(row, dict):
                deleted_count = row.get("cnt", 0)

        # Delete all nodes and relationships
        delete_query = "MATCH (n) DETACH DELETE n"
        await driver.execute_query(delete_query)
        await driver.close()

        # Reset singleton state so indices are rebuilt on next use
        if _global_graphiti is not None:
            await _global_graphiti.close()
        _global_graphiti = None
        _global_driver = None
        _graphiti_initialized = False

        logger.info(
            f"Global graph {GLOBAL_GRAPH_NAME} reset successfully ({deleted_count} nodes deleted)"
        )
        return (True, deleted_count)

    except Exception as e:
        logger.error(f"Failed to reset global graph: {e}")
        return (False, 0)
