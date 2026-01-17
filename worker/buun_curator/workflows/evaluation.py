"""
RAGAS Evaluation Workflows.

Workflows for evaluating AI responses using RAGAS metrics and recording to Langfuse.
Includes:
- EvaluationWorkflow: For agent/research Q&A evaluation
- SummarizationEvaluationWorkflow: For content summarization evaluation
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities.evaluation import (
        EvaluateRagasInput,
        EvaluateRagasOutput,
        EvaluateSummarizationInput,
        EvaluateSummarizationOutput,
        SummarizeItem,
        evaluate_ragas,
        evaluate_summarization,
    )
    from buun_curator.models.workflow_io import (
        EvaluationInput,
        EvaluationResult,
        SummarizationEvaluationInput,
        SummarizationEvaluationResult,
    )


@workflow.defn
class EvaluationWorkflow:
    """
    Workflow for RAGAS evaluation.

    Evaluates AI responses using RAGAS metrics (Faithfulness, Response Relevancy)
    and records the scores to Langfuse.
    """

    @workflow.run
    async def run(self, input: EvaluationInput) -> EvaluationResult:
        """
        Run the evaluation workflow.

        Parameters
        ----------
        input : EvaluationInput
            Workflow input containing trace_id, question, contexts, and answer.

        Returns
        -------
        EvaluationResult
            Result containing evaluation scores and status.
        """
        wf_info = workflow.info()
        workflow.logger.info(
            "EvaluationWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "trace_id": input.trace_id,
                "mode": input.mode,
                "question_len": len(input.question),
            },
        )

        # Execute the evaluation activity
        result: EvaluateRagasOutput = await workflow.execute_activity(
            evaluate_ragas,
            EvaluateRagasInput(
                trace_id=input.trace_id,
                question=input.question,
                contexts=input.contexts,
                answer=input.answer,
            ),
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=5),
            ),
        )

        workflow.logger.info(
            "EvaluationWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "success": result.success,
                "scores": result.scores,
            },
        )

        return EvaluationResult(
            trace_id=input.trace_id,
            mode=input.mode,
            scores=result.scores,
            success=result.success,
            error=result.error,
        )


@workflow.defn
class SummarizationEvaluationWorkflow:
    """
    Workflow for summarization evaluation.

    Evaluates content summarization quality using RAGAS metrics
    (Faithfulness, Response Relevancy) and records the scores to Langfuse.
    Designed to be called fire-and-forget from ContentDistillationWorkflow.
    """

    @workflow.run
    async def run(self, input: SummarizationEvaluationInput) -> SummarizationEvaluationResult:
        """
        Run the summarization evaluation workflow.

        Parameters
        ----------
        input : SummarizationEvaluationInput
            Workflow input containing trace_id and summarization items.

        Returns
        -------
        SummarizationEvaluationResult
            Result containing average evaluation scores and status.
        """
        wf_info = workflow.info()
        workflow.logger.info(
            "SummarizationEvaluationWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "trace_id": input.trace_id,
                "items": len(input.items),
            },
        )

        # Convert workflow items to activity items
        # Note: Only entry_id and trace_id are passed; content is fetched by activity
        activity_items = [
            SummarizeItem(
                entry_id=item.entry_id,
                trace_id=item.trace_id,
            )
            for item in input.items
        ]

        # Execute the evaluation activity
        result: EvaluateSummarizationOutput = await workflow.execute_activity(
            evaluate_summarization,
            EvaluateSummarizationInput(
                trace_id=input.trace_id,
                items=activity_items,
                max_samples=input.max_samples,
            ),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=5),
            ),
        )

        workflow.logger.info(
            "SummarizationEvaluationWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "success": result.success,
                "evaluated": result.evaluated_count,
                "scores": result.average_scores,
            },
        )

        return SummarizationEvaluationResult(
            trace_id=input.trace_id,
            average_scores=result.average_scores,
            evaluated_count=result.evaluated_count,
            success=result.success,
            error=result.error,
        )
