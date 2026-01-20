"""
RAGAS evaluation activities.

Activities for computing RAGAS metrics and recording them to Langfuse.
Supports both agent/research evaluation and summarization evaluation.
"""

from statistics import mean

from pydantic import BaseModel
from temporalio import activity

from buun_curator.logging import get_logger

logger = get_logger(__name__)

# Default question for summarization evaluation
SUMMARIZE_QUESTION = "Summarize this content concisely."


class EvaluateRagasInput(BaseModel):
    """Input for evaluate_ragas activity."""

    trace_id: str
    question: str
    contexts: list[str]
    answer: str


class EvaluateRagasOutput(BaseModel):
    """Output for evaluate_ragas activity."""

    scores: dict[str, float]
    success: bool
    error: str = ""


class SummarizeItem(BaseModel):
    """
    Single item for summarization evaluation.

    Note: Only entry_id and trace_id are passed to avoid large data in activity input.
    The activity fetches content from the database using entry_id.
    """

    entry_id: str
    trace_id: str = ""  # Per-entry trace_id for Langfuse


class EvaluateSummarizationInput(BaseModel):
    """Input for evaluate_summarization activity."""

    trace_id: str
    items: list[SummarizeItem]
    max_samples: int = 5  # Max entries to evaluate (for cost control)


class EvaluateSummarizationOutput(BaseModel):
    """Output for evaluate_summarization activity."""

    average_scores: dict[str, float]
    evaluated_count: int
    success: bool
    error: str = ""


@activity.defn
async def evaluate_ragas(input: EvaluateRagasInput) -> EvaluateRagasOutput:
    """
    Evaluate a sample using RAGAS metrics and record to Langfuse.

    Parameters
    ----------
    input : EvaluateRagasInput
        Contains trace_id, question, contexts, and answer.

    Returns
    -------
    EvaluateRagasOutput
        Result containing scores and success status.

    Raises
    ------
    Exception
        Re-raises any exception to mark the workflow as Failed in Temporal.
    """
    from buun_curator.services.evaluation import score_and_record

    logger.info(
        "Starting RAGAS evaluation",
        trace_id=input.trace_id,
        question_len=len(input.question),
        contexts_count=len(input.contexts),
    )

    scores = await score_and_record(
        trace_id=input.trace_id,
        question=input.question,
        contexts=input.contexts,
        answer=input.answer,
    )

    logger.info("RAGAS evaluation completed", trace_id=input.trace_id, scores=scores)

    return EvaluateRagasOutput(
        scores=scores,
        success=True,
    )


@activity.defn
async def evaluate_summarization(
    input: EvaluateSummarizationInput,
) -> EvaluateSummarizationOutput:
    """
    Evaluate summarization quality using RAGAS metrics.

    Evaluates up to max_samples summaries and records average scores to Langfuse.
    Uses "Summarize this content" as the question, original content as context,
    and the summary as the answer.

    Fetches entry content from the database to avoid passing large data through
    workflow/activity inputs (which can cause Temporal deadlock errors).

    Parameters
    ----------
    input : EvaluateSummarizationInput
        Contains trace_id and list of (entry_id, trace_id) items.

    Returns
    -------
    EvaluateSummarizationOutput
        Result containing average scores and success status.
    """
    from buun_curator.config import get_config
    from buun_curator.services.api import APIClient
    from buun_curator.services.evaluation import add_ragas_scores, score_single

    if not input.items:
        logger.info("No items to evaluate for summarization")
        return EvaluateSummarizationOutput(
            average_scores={},
            evaluated_count=0,
            success=True,
        )

    # Sample items if there are too many
    items_to_evaluate = input.items[: input.max_samples]
    logger.info(
        "Starting summarization evaluation",
        trace_id=input.trace_id,
        items_evaluated=len(items_to_evaluate),
        items_total=len(input.items),
    )

    # Fetch entry content from database
    config = get_config()
    async with APIClient(config.api_url, config.api_token) as api:
        # Build entry_id -> (original_content, summary) mapping
        entry_data: dict[str, tuple[str, str]] = {}
        for item in items_to_evaluate:
            entry = await api.get_entry(item.entry_id)
            if entry and "error" not in entry:
                original_content = entry.get("fullContent", "")
                summary = entry.get("summary", "")
                if original_content and summary:
                    entry_data[item.entry_id] = (original_content, summary)
                else:
                    logger.warning(
                        "Entry missing content or summary, skipping", entry_id=item.entry_id
                    )
            else:
                logger.warning("Failed to fetch entry, skipping", entry_id=item.entry_id)

    if not entry_data:
        logger.warning("No entries with valid content/summary found")
        return EvaluateSummarizationOutput(
            average_scores={},
            evaluated_count=0,
            success=True,
        )

    # Collect scores from all items
    all_scores: dict[str, list[float]] = {}
    evaluated_count = 0

    for item in items_to_evaluate:
        if item.entry_id not in entry_data:
            continue

        original_content, summary = entry_data[item.entry_id]
        # Use per-entry trace_id if available, fallback to input.trace_id
        item_trace_id = item.trace_id or input.trace_id
        try:
            scores = await score_single(
                question=SUMMARIZE_QUESTION,
                contexts=[original_content],
                answer=summary,
                trace_id=item_trace_id,
            )

            for metric_name, score_value in scores.items():
                if score_value >= 0:  # Skip failed metrics
                    if metric_name not in all_scores:
                        all_scores[metric_name] = []
                    all_scores[metric_name].append(score_value)

            # Record per-entry scores to Langfuse
            if scores and item_trace_id:
                await add_ragas_scores(item_trace_id, scores)

            logger.debug("Evaluated entry", entry_id=item.entry_id, scores=scores)
            evaluated_count += 1

        except Exception as e:
            logger.warning(f"Failed to evaluate entry: {e}", entry_id=item.entry_id)

    # Calculate averages
    average_scores: dict[str, float] = {}
    for metric_name, scores_list in all_scores.items():
        if scores_list:
            avg = mean(scores_list)
            # Use "batch_" prefix to indicate batch average scores
            prefixed_name = f"batch_{metric_name}"
            average_scores[prefixed_name] = avg
            logger.info(
                "Average score",
                metric=prefixed_name,
                avg=round(avg, 3),
                count=len(scores_list),
            )

    # Record average scores to Langfuse
    if average_scores:
        await add_ragas_scores(input.trace_id, average_scores)

    logger.info(
        "Summarization evaluation completed",
        trace_id=input.trace_id,
        evaluated_count=evaluated_count,
        scores=average_scores,
    )

    return EvaluateSummarizationOutput(
        average_scores=average_scores,
        evaluated_count=evaluated_count,
        success=True,
    )
