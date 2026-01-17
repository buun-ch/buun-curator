"""
Preview Fetch Workflow.

Fetches content from a single URL for preview purposes.
Used when testing extraction rules in the AI assistant.
"""

from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import fetch_single_content
    from buun_curator.models import (
        FetchSingleContentInput,
        FetchSingleContentOutput,
        PreviewFetchInput,
    )
    from buun_curator.models.workflow_io import PreviewFetchResult


@workflow.defn
class PreviewFetchWorkflow:
    """
    Workflow for fetching content from a single URL for preview.
    """

    @workflow.run
    async def run(
        self,
        input: PreviewFetchInput,
    ) -> PreviewFetchResult:
        """
        Run the preview fetch workflow.

        Parameters
        ----------
        input : PreviewFetchInput
            Workflow input containing URL and options.

        Returns
        -------
        PreviewFetchResult
            Result containing fetched content or error.
        """
        # Extract input fields for convenience
        url = input.url
        title = input.title
        feed_extraction_rules = input.feed_extraction_rules
        additional_extraction_rules = input.additional_extraction_rules
        timeout = input.timeout

        wf_info = workflow.info()
        workflow.logger.info(
            "PreviewFetchWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "url": url,
            },
        )

        try:
            result: FetchSingleContentOutput = await workflow.execute_activity(
                fetch_single_content,
                FetchSingleContentInput(
                    url=url,
                    title=title,
                    timeout=timeout,
                    feed_extraction_rules=feed_extraction_rules,
                    additional_extraction_rules=additional_extraction_rules,
                ),
                start_to_close_timeout=timedelta(seconds=timeout + 30),
            )

            if result.full_content:
                workflow.logger.info(
                    "PreviewFetchWorkflow end",
                    extra={
                        "workflow_id": wf_info.workflow_id,
                        "content_length": len(result.full_content),
                    },
                )
                return PreviewFetchResult(
                    status="success",
                    full_content=result.full_content,
                )
            else:
                workflow.logger.warning(
                    "PreviewFetchWorkflow end (empty content)",
                    extra={"workflow_id": wf_info.workflow_id},
                )
                return PreviewFetchResult(
                    status="empty",
                    error="No content extracted from URL",
                )

        except Exception as e:
            workflow.logger.error(
                f"PreviewFetchWorkflow failed: {e}",
                extra={"workflow_id": wf_info.workflow_id},
            )
            return PreviewFetchResult(
                status="error",
                error=str(e),
            )
