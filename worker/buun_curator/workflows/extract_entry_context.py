"""
Extract Entry Context Workflow.

Sub-Workflow for extracting structured context from an entry.
Can be called independently or as a child workflow.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.api import get_entry, save_entry_context
    from buun_curator.activities.context.extract_context import extract_entry_context
    from buun_curator.activities.graph_rag_session import (
        add_to_graph_rag_session,
        reset_graph_rag_session,
    )
    from buun_curator.models import (
        AddToGraphRAGSessionInput,
        ExtractEntryContextActivityInput,
        ExtractEntryContextInput,
        GetEntryInput,
        ResetGraphRAGSessionInput,
        SaveEntryContextInput,
    )
    from buun_curator.models.context import EntryContext
    from buun_curator.services.content import html_to_markdown


def _get_content(entry: dict) -> str:
    """
    Get content for context extraction from an entry.

    Tries fullContent first, then filteredContent, then feedContent (converted from HTML).
    """
    content = entry.get("filteredContent") or ""
    if content.strip():
        return content

    content = entry.get("fullContent") or ""
    if content.strip():
        return content

    # Fallback to feedContent (HTML) converted to Markdown
    feed_content = entry.get("feedContent") or ""
    if feed_content.strip():
        return html_to_markdown(feed_content)

    return ""


@workflow.defn
class ExtractEntryContextWorkflow:
    """
    Sub-Workflow for extracting structured context from an entry.

    Can be called independently or as a child workflow from ContextCollectionWorkflow.
    Fetches entry data via get_entry Activity, then extracts context via LLM.
    """

    @workflow.run
    async def run(self, input: ExtractEntryContextInput) -> EntryContext | None:
        """
        Execute entry context extraction.

        Parameters
        ----------
        input : ExtractEntryContextInput
            Input containing entry_id.

        Returns
        -------
        EntryContext | None
            Comprehensive structured context extracted from the entry,
            or None if entry not found or has no content.
        """
        workflow.logger.info(
            "ExtractEntryContextWorkflow start",
            extra={"entry_id": input.entry_id},
        )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(seconds=60),
            maximum_attempts=3,
        )

        # Step 1: Fetch entry data
        entry_result = await workflow.execute_activity(
            get_entry,
            GetEntryInput(entry_id=input.entry_id),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        entry = entry_result.entry
        if not entry or "error" in entry:
            workflow.logger.warning(f"Entry not found: {input.entry_id}")
            return None

        # Step 2: Extract content
        content = _get_content(entry)
        if not content:
            workflow.logger.warning(f"Entry {input.entry_id} has no content")
            return None

        title = entry.get("title", "")
        url = entry.get("url", "")

        workflow.logger.info(
            f"Extracting context for {input.entry_id}: {title[:50]}... ({len(content)} chars)"
        )

        # Step 3: Execute context extraction Activity
        context = await workflow.execute_activity(
            extract_entry_context,
            ExtractEntryContextActivityInput(
                entry_id=input.entry_id,
                title=title,
                url=url,
                content=content,
            ),
            start_to_close_timeout=timedelta(seconds=120),  # LLM can be slow
            retry_policy=retry_policy,
        )

        if context is None:
            workflow.logger.warning(f"No context extracted for {input.entry_id}")
            return None

        # Step 4: Save context to database
        workflow.logger.info(f"Saving context for {input.entry_id}")
        save_result = await workflow.execute_activity(
            save_entry_context,
            SaveEntryContextInput(
                entry_id=input.entry_id,
                context=context.model_dump(),
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry_policy,
        )

        if not save_result.success:
            workflow.logger.error(
                f"Failed to save context for {input.entry_id}: {save_result.error}"
            )

        # Step 5: Reset and add entry content to GraphRAG session for Deep Research
        # First reset any existing session to ensure clean state
        await workflow.execute_activity(
            reset_graph_rag_session,
            ResetGraphRAGSessionInput(entry_id=input.entry_id),
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=retry_policy,
        )

        # Then add the content
        workflow.logger.info(f"Adding content to Graphiti session for {input.entry_id}")
        graph_rag_result = await workflow.execute_activity(
            add_to_graph_rag_session,
            AddToGraphRAGSessionInput(
                entry_id=input.entry_id,
                content=content,
                source_type="entry",
            ),
            start_to_close_timeout=timedelta(seconds=120),
            retry_policy=retry_policy,
        )

        if not graph_rag_result.success:
            workflow.logger.warning(
                f"Failed to add to Graphiti session for {input.entry_id}: {graph_rag_result.error}"
            )

        workflow.logger.info(
            "ExtractEntryContextWorkflow end",
            extra={"entry_id": input.entry_id},
        )
        return context
