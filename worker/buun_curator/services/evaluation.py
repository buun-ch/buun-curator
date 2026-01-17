"""
RAGAS evaluation service for Langfuse score recording.

Provides functionality to compute RAGAS metrics and record them to Langfuse.
"""

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langfuse import Langfuse
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings import LangchainEmbeddingsWrapper
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import Faithfulness, ResponseRelevancy

from buun_curator.config import get_config
from buun_curator.logging import get_logger

logger = get_logger(__name__)

# Cached Langfuse client
_langfuse_client: Langfuse | None = None


def get_langfuse_client() -> Langfuse:
    """
    Get Langfuse client with direct connection.

    Returns
    -------
    Langfuse
        Langfuse client instance.

    Raises
    ------
    ValueError
        If Langfuse credentials are not configured.
    """
    global _langfuse_client

    if _langfuse_client is not None:
        return _langfuse_client

    config = get_config()

    if not config.langfuse_public_key or not config.langfuse_secret_key:
        raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are required")

    _langfuse_client = Langfuse(
        public_key=config.langfuse_public_key,
        secret_key=config.langfuse_secret_key,
        host=config.langfuse_host or None,
    )
    return _langfuse_client


def get_ragas_llm(
    trace_id: str | None = None,
    trace_name: str | None = None,
) -> LangchainLLMWrapper:  # type: ignore[type-arg]
    """
    Get LLM for RAGAS evaluation.

    Parameters
    ----------
    trace_id : str | None
        Trace ID for Langfuse tracking. If provided, LLM calls attach to this trace.
    trace_name : str | None
        Trace name for Langfuse. Only used when trace_id is not provided.

    Returns
    -------
    LangchainLLMWrapper
        Wrapped LLM for RAGAS.
    """
    config = get_config()

    # Build extra_body with metadata for LiteLLM/Langfuse tracing
    # See: https://docs.litellm.ai/docs/observability/langfuse_integration
    # Use existing_trace_id to attach to an existing trace without changing its name
    extra_body = None
    if trace_id:
        extra_body = {
            "metadata": {
                "existing_trace_id": trace_id,
                "generation_name": "ragas-evaluation",
            }
        }
    elif trace_name:
        extra_body = {
            "metadata": {
                "trace_name": trace_name,
                "generation_name": trace_name,
            }
        }

    llm = ChatOpenAI(
        model=config.llm_model,
        temperature=0,
        api_key=config.openai_api_key,  # type: ignore[arg-type]
        base_url=config.openai_base_url or None,
        extra_body=extra_body,
    )

    return LangchainLLMWrapper(llm)


def get_ragas_embeddings() -> LangchainEmbeddingsWrapper:  # type: ignore[type-arg]
    """
    Get embeddings for RAGAS evaluation using sentence-transformers.

    Returns
    -------
    LangchainEmbeddingsWrapper
        Wrapped embeddings for RAGAS.
    """
    config = get_config()
    embeddings = HuggingFaceEmbeddings(model_name=config.evaluation_embedding_model)
    return LangchainEmbeddingsWrapper(embeddings)


def get_metrics(trace_id: str | None = None) -> list:
    """
    Get evaluation metrics.

    Parameters
    ----------
    trace_id : str | None
        Trace ID for Langfuse tracking.

    Returns
    -------
    list
        List of RAGAS metrics configured with LLM and embeddings.
    """
    llm = get_ragas_llm(trace_id=trace_id)
    embeddings = get_ragas_embeddings()

    return [
        Faithfulness(llm=llm, max_retries=3),
        ResponseRelevancy(llm=llm, embeddings=embeddings),
    ]


async def score_single(
    question: str,
    contexts: list[str],
    answer: str,
    trace_id: str | None = None,
) -> dict[str, float]:
    """
    Score a single sample using RAGAS metrics.

    Parameters
    ----------
    question : str
        The user's question.
    contexts : list[str]
        Retrieved context documents.
    answer : str
        The generated answer.
    trace_id : str | None
        Trace ID for Langfuse tracking.

    Returns
    -------
    dict[str, float]
        Dictionary mapping metric names to scores.
    """
    metrics = get_metrics(trace_id=trace_id)
    scores: dict[str, float] = {}

    sample = SingleTurnSample(
        user_input=question,
        retrieved_contexts=contexts,
        response=answer,
    )

    for metric in metrics:
        try:
            score = await metric.single_turn_ascore(sample)
            scores[metric.name] = score
            logger.debug("RAGAS metric computed", metric=metric.name, score=round(score, 3))
        except Exception as e:
            logger.warning(f"Failed to compute metric: {e}", metric=metric.name)
            scores[metric.name] = -1.0  # Indicate failure

    return scores


async def add_ragas_scores(
    trace_id: str,
    scores: dict[str, float],
) -> None:
    """
    Add RAGAS scores to Langfuse via direct connection.

    Parameters
    ----------
    trace_id : str
        The trace ID to associate scores with.
    scores : dict[str, float]
        Dictionary mapping metric names to scores.
    """
    try:
        logger.info("Adding RAGAS scores to Langfuse", trace_id=trace_id, scores=scores)
        langfuse = get_langfuse_client()

        for metric_name, score_value in scores.items():
            if score_value < 0:
                # Skip failed metrics
                logger.debug("Skipping failed metric", metric=metric_name, score=score_value)
                continue

            logger.debug("Creating score", metric=metric_name, score=score_value)
            langfuse.create_score(
                trace_id=trace_id,
                name=metric_name,
                value=score_value,
                comment=f"RAGAS {metric_name} score",
            )

        # Flush buffered data
        logger.debug("Flushing Langfuse data")
        langfuse.flush()
        logger.info("Added RAGAS scores to trace", count=len(scores), trace_id=trace_id)

    except Exception:
        logger.exception("Failed to add RAGAS scores to Langfuse")


async def score_and_record(
    trace_id: str,
    question: str,
    contexts: list[str],
    answer: str,
) -> dict[str, float]:
    """
    Score a sample and record to Langfuse.

    Parameters
    ----------
    trace_id : str
        The trace ID to attach scores to.
    question : str
        The user's question.
    contexts : list[str]
        Retrieved context documents.
    answer : str
        The generated answer.

    Returns
    -------
    dict[str, float]
        Dictionary mapping metric names to scores.
    """
    # Compute RAGAS scores (pass trace_id for LLM call tracking)
    scores = await score_single(question, contexts, answer, trace_id=trace_id)

    # Add scores to Langfuse
    await add_ragas_scores(trace_id, scores)

    return scores
