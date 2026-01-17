"""
Global Graph Update Workflow.

Updates the global knowledge graph with pending entries in batches.
Designed to run on a schedule to periodically process new entries.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        add_to_global_graph_bulk,
        get_entries_for_graph_update,
        get_entry,
        mark_entries_graph_added,
    )
    from buun_curator.models import (
        AddToGlobalGraphBulkInput,
        AddToGlobalGraphBulkOutput,
        GetEntriesForGraphUpdateInput,
        GetEntriesForGraphUpdateOutput,
        GetEntryInput,
        GetEntryOutput,
        GraphEpisodeInput,
        MarkEntriesGraphAddedInput,
        MarkEntriesGraphAddedOutput,
    )
    from buun_curator.models.workflow_io import (
        GlobalGraphUpdateInput,
        GlobalGraphUpdateResult,
    )


@workflow.defn
class GlobalGraphUpdateWorkflow:
    """
    Workflow for updating the global knowledge graph.

    Fetches entries that haven't been added to the graph yet,
    builds episodes from their filtered content, and adds them in bulk.
    """

    @workflow.run
    async def run(self, input: GlobalGraphUpdateInput) -> GlobalGraphUpdateResult:
        """
        Execute the global graph update workflow.

        Parameters
        ----------
        input : GlobalGraphUpdateInput
            Configuration including optional entry_ids and batch_size.

        Returns
        -------
        GlobalGraphUpdateResult
            Status and counts of processed entries.
        """
        wf_info = workflow.info()
        workflow.logger.info(
            "GlobalGraphUpdateWorkflow start",
            extra={"workflow_id": wf_info.workflow_id},
        )
        workflow.logger.info(
            "GlobalGraphUpdateWorkflow options",
            extra={
                "entry_ids": len(input.entry_ids),
                "batch_size": input.batch_size,
            },
        )

        total_added = 0
        total_count = 0

        # Fetch pending entries (let exceptions propagate to fail the workflow)
        if input.entry_ids:
            # Process specific entries
            entry_ids = input.entry_ids
            total_count = len(entry_ids)
        else:
            # Fetch pending entries
            fetch_result: GetEntriesForGraphUpdateOutput = (
                await workflow.execute_activity(
                    get_entries_for_graph_update,
                    GetEntriesForGraphUpdateInput(batch_size=input.batch_size),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
            )
            entry_ids = fetch_result.entry_ids
            total_count = fetch_result.total_count

        if not entry_ids:
            workflow.logger.info("No entries pending graph update")
            return GlobalGraphUpdateResult(
                status="completed",
                added_count=0,
                total_count=0,
            )

        workflow.logger.info(
            f"Processing {len(entry_ids)} entries "
            f"(total pending: {total_count})"
        )

        # Fetch entry details and build episodes
        episodes: list[GraphEpisodeInput] = []
        processed_ids: list[str] = []

        for entry_id in entry_ids:
            try:
                entry_result: GetEntryOutput = await workflow.execute_activity(
                    get_entry,
                    GetEntryInput(entry_id=entry_id),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )

                entry = entry_result.entry
                if not entry:
                    workflow.logger.warning(f"Entry not found: {entry_id}")
                    continue

                # Use filtered_content for the graph
                content = entry.get("filteredContent", "")
                if not content:
                    workflow.logger.debug(
                        f"Skipping entry {entry_id}: no filteredContent"
                    )
                    # Still mark as processed to avoid reprocessing
                    processed_ids.append(entry_id)
                    continue

                episodes.append(
                    GraphEpisodeInput(
                        entry_id=entry_id,
                        content=content,
                        title=entry.get("title"),
                        url=entry.get("url"),
                        source_type="entry",
                    )
                )
                processed_ids.append(entry_id)

            except Exception as e:
                workflow.logger.warning(
                    f"Failed to fetch entry {entry_id}: {e}"
                )

        # Add episodes to graph in bulk (let exceptions propagate to fail the workflow)
        if episodes:
            bulk_result: AddToGlobalGraphBulkOutput = (
                await workflow.execute_activity(
                    add_to_global_graph_bulk,
                    AddToGlobalGraphBulkInput(episodes=episodes),
                    start_to_close_timeout=timedelta(minutes=10),
                    retry_policy=RetryPolicy(
                        maximum_attempts=2,
                        initial_interval=timedelta(seconds=5),
                    ),
                )
            )
            total_added = bulk_result.success_count
            workflow.logger.info(
                f"Added {bulk_result.success_count} entries to global graph "
                f"(failed: {bulk_result.failed_count})"
            )

        # Mark entries as graph-added (let exceptions propagate to fail the workflow)
        if processed_ids:
            mark_result: MarkEntriesGraphAddedOutput = (
                await workflow.execute_activity(
                    mark_entries_graph_added,
                    MarkEntriesGraphAddedInput(entry_ids=processed_ids),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=3),
                )
            )
            workflow.logger.info(
                f"Marked {mark_result.updated_count} entries as graph-added"
            )

        workflow.logger.info(
            f"Completed: added {total_added} entries to graph"
        )
        workflow.logger.info(
            "GlobalGraphUpdateWorkflow end",
            extra={"workflow_id": wf_info.workflow_id},
        )

        return GlobalGraphUpdateResult(
            status="completed",
            added_count=total_added,
            total_count=total_count,
        )
