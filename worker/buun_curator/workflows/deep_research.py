"""
DeepResearchWorkflow for GraphRAG-based knowledge graph research.

Build a knowledge graph from entry content and search it with a query
using Graphiti as the GraphRAG backend.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        add_to_graph_rag_session,
        build_graph_rag_graph,
        get_entry,
        reset_graph_rag_session,
        search_graph_rag_session,
    )
    from buun_curator.models.activity_io import (
        AddToGraphRAGSessionInput,
        BuildGraphRAGGraphInput,
        GetEntryInput,
        ResetGraphRAGSessionInput,
        SearchGraphRAGSessionInput,
    )
    from buun_curator.models.workflow_io import DeepResearchInput, DeepResearchResult


@workflow.defn
class DeepResearchWorkflow:
    """Build knowledge graph and search with query using Graphiti."""

    @workflow.run
    async def run(self, input: DeepResearchInput) -> DeepResearchResult:
        """
        Execute deep research workflow.

        Steps:
        1. Fetch entry content from API
        2. Reset existing session (if any) and add entry content
        3. Build knowledge graph (no-op for Graphiti, built incrementally)
        4. Search the graph with the query

        Parameters
        ----------
        input : DeepResearchInput
            Entry ID, query, and search mode.

        Returns
        -------
        DeepResearchResult
            Status, search results, and optional error.
        """
        workflow.logger.info(
            "DeepResearchWorkflow start",
            extra={
                "entry_id": input.entry_id,
                "query": input.query,
                "search_mode": input.search_mode,
            },
        )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
        )

        try:
            # Step 1: Fetch entry content from API
            workflow.logger.info("Fetching entry content...")
            entry_result = await workflow.execute_activity(
                get_entry,
                GetEntryInput(entry_id=input.entry_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            entry = entry_result.entry
            if not entry or "error" in entry:
                error_msg = entry.get("error", "Entry not found") if entry else "Entry not found"
                workflow.logger.error(
                    f"Failed to fetch entry: {error_msg}",
                    extra={"entry_id": input.entry_id},
                )
                return DeepResearchResult(
                    status="error",
                    error=f"Failed to fetch entry: {error_msg}",
                )

            # Extract content (priority: fullContent > filteredContent > feedContent)
            content = entry.get("fullContent") or entry.get("filteredContent") or ""
            if not content:
                # Fallback to feedContent (HTML)
                content = entry.get("feedContent") or ""

            if not content:
                workflow.logger.error("Entry has no content")
                return DeepResearchResult(
                    status="error",
                    error="Entry has no content to analyze",
                )

            workflow.logger.info("Entry content loaded", extra={"content_length": len(content)})

            # Step 2: Reset session and add entry content
            workflow.logger.info("Resetting and adding content to Graphiti session...")
            await workflow.execute_activity(
                reset_graph_rag_session,
                ResetGraphRAGSessionInput(entry_id=input.entry_id),
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy,
            )

            add_result = await workflow.execute_activity(
                add_to_graph_rag_session,
                AddToGraphRAGSessionInput(
                    entry_id=input.entry_id,
                    content=content,
                    source_type="entry",
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            if not add_result.success:
                workflow.logger.error(
                    f"Add content failed: {add_result.error}",
                    extra={"entry_id": input.entry_id},
                )
                return DeepResearchResult(
                    status="error",
                    error=add_result.error or "Failed to add content to session",
                )

            # Step 3: Build knowledge graph (no-op for Graphiti)
            workflow.logger.info("Building Graphiti knowledge graph...")
            build_result = await workflow.execute_activity(
                build_graph_rag_graph,
                BuildGraphRAGGraphInput(entry_id=input.entry_id),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=retry_policy,
            )

            if not build_result.success:
                workflow.logger.error(
                    f"Build graph failed: {build_result.error}",
                    extra={"entry_id": input.entry_id},
                )
                return DeepResearchResult(
                    status="error",
                    error=build_result.error or "Failed to build knowledge graph",
                )

            workflow.logger.info("Graph built", extra={"graph_name": build_result.graph_name})

            # Step 4: Search the knowledge graph
            workflow.logger.info(
                "Searching Graphiti graph", extra={"search_mode": input.search_mode}
            )
            search_result = await workflow.execute_activity(
                search_graph_rag_session,
                SearchGraphRAGSessionInput(
                    entry_id=input.entry_id,
                    query=input.query,
                    search_mode=input.search_mode,
                    top_k=10,
                ),
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )

            if not search_result.success:
                workflow.logger.error(
                    f"Search failed: {search_result.error}",
                    extra={"entry_id": input.entry_id},
                )
                return DeepResearchResult(
                    status="error",
                    error=search_result.error or "Failed to search knowledge graph",
                )

            workflow.logger.info(
                "DeepResearchWorkflow end",
                extra={"entry_id": input.entry_id, "results": len(search_result.results)},
            )

            return DeepResearchResult(
                status="completed",
                results=search_result.results,
            )

        except Exception as e:
            workflow.logger.error(f"DeepResearch failed: {e}", extra={"entry_id": input.entry_id})
            return DeepResearchResult(
                status="error",
                error=str(e),
            )
