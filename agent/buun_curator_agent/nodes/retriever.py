"""Retriever node for Deep Research LangGraph."""

import asyncio
from typing import cast

from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import (
    ResearchState,
    RetrievedDoc,
    SearchMode,
    SearchSource,
)
from buun_curator_agent.tools.embedding import search_entries_by_embedding
from buun_curator_agent.tools.search import search_entries

logger = get_logger(__name__)


def _determine_sources(state: ResearchState) -> list[SearchSource]:
    """
    Determine which sources to use based on search mode.

    Parameters
    ----------
    state : ResearchState
        Current graph state.

    Returns
    -------
    list[SearchSource]
        List of sources to search.
    """
    search_mode = cast(SearchMode | None, state.get("search_mode")) or "planner"
    plan = state.get("plan")

    if search_mode == "meilisearch":
        return ["meilisearch"]
    elif search_mode == "embedding":
        return ["embedding"]
    elif search_mode == "hybrid":
        return ["meilisearch", "embedding"]
    else:  # planner
        if plan and plan.sources:
            return list(plan.sources)
        return ["meilisearch"]  # fallback


async def _search_meilisearch(
    queries: list[str],
    limit_per_query: int = 5,
) -> list[RetrievedDoc]:
    """
    Execute Meilisearch queries in parallel.

    Parameters
    ----------
    queries : list[str]
        Search queries.
    limit_per_query : int, optional
        Max results per query (default: 5).

    Returns
    -------
    list[RetrievedDoc]
        Retrieved documents.
    """
    tasks = [search_entries(query, limit=limit_per_query) for query in queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    docs: list[RetrievedDoc] = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            logger.error(
                f"Meilisearch search failed: {result}",
                query=queries[i],
                error_type=type(result).__name__,
            )
            continue
        docs.extend(result)

    return docs


async def _search_embedding(
    queries: list[str],
    limit_per_query: int = 5,
    threshold: float = 0.8,
) -> list[RetrievedDoc]:
    """
    Execute embedding searches in parallel.

    Parameters
    ----------
    queries : list[str]
        Search queries.
    limit_per_query : int, optional
        Max results per query (default: 5).
    threshold : float, optional
        Max cosine distance (default: 0.8).

    Returns
    -------
    list[RetrievedDoc]
        Retrieved documents.
    """
    tasks = [
        search_entries_by_embedding(query, limit=limit_per_query, threshold=threshold)
        for query in queries
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    docs: list[RetrievedDoc] = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            logger.error(
                f"Embedding search failed: {result}",
                query=queries[i],
                error_type=type(result).__name__,
            )
            continue
        docs.extend(result)

    return docs


async def retriever_node(state: ResearchState) -> ResearchState:
    """
    Retriever node: execute searches based on the plan and search mode.

    Parameters
    ----------
    state : ResearchState
        Current graph state with search plan.

    Returns
    -------
    ResearchState
        Updated state with retrieved documents.
    """
    plan = state.get("plan")
    search_mode = cast(SearchMode | None, state.get("search_mode")) or "planner"

    if not plan:
        logger.warning("No plan found, skipping retrieval", query=state["query"][:50])
        return ResearchState(
            query=state["query"],
            entry_context=state["entry_context"],
            search_mode=search_mode,
            plan=None,
            retrieved_docs=[],
            final_answer=state.get("final_answer", ""),
            iteration=state.get("iteration", 0),
            needs_more_info=state.get("needs_more_info", False),
            trace_id=state.get("trace_id"),
            session_id=state.get("session_id"),
        )

    sources = _determine_sources(state)
    logger.info(
        "Starting retrieval search",
        mode=search_mode,
        sources=sources,
        query_count=len(plan.sub_queries),
    )

    all_docs: list[RetrievedDoc] = []
    seen_ids: set[str] = set()

    # Execute searches for each source in parallel
    search_tasks: list[asyncio.Task[list[RetrievedDoc]]] = []

    if "meilisearch" in sources:
        search_tasks.append(
            asyncio.create_task(_search_meilisearch(plan.sub_queries, limit_per_query=5))
        )

    if "embedding" in sources:
        search_tasks.append(
            asyncio.create_task(_search_embedding(plan.sub_queries, limit_per_query=5))
        )

    if search_tasks:
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, BaseException):
                logger.error(
                    f"Search task failed: {result}",
                    error_type=type(result).__name__,
                )
                continue
            for doc in result:
                if doc.id not in seen_ids:
                    seen_ids.add(doc.id)
                    all_docs.append(doc)

    logger.info("Retrieved documents", doc_count=len(all_docs))

    return ResearchState(
        query=state["query"],
        entry_context=state["entry_context"],
        search_mode=search_mode,
        plan=plan,
        retrieved_docs=all_docs,
        final_answer=state.get("final_answer", ""),
        iteration=state.get("iteration", 0),
        needs_more_info=state.get("needs_more_info", False),
        trace_id=state.get("trace_id"),
        session_id=state.get("session_id"),
    )
