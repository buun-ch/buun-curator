"""
Temporal client configuration for Agent service.

Provides a configured Temporal client with Pydantic v2 data converter support.
"""

import uuid

from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from buun_curator_agent.config import settings
from buun_curator_agent.logging import get_logger

logger = get_logger(__name__)

# Cached Temporal client
_temporal_client: Client | None = None


async def get_temporal_client() -> Client:
    """
    Get or create a Temporal client with Pydantic v2 data converter.

    Returns
    -------
    Client
        Configured Temporal client.
    """
    global _temporal_client

    if _temporal_client is not None:
        return _temporal_client

    logger.info(
        "Connecting to Temporal",
        host=settings.temporal_host,
        namespace=settings.temporal_namespace,
    )

    _temporal_client = await Client.connect(
        settings.temporal_host,
        namespace=settings.temporal_namespace,
        data_converter=pydantic_data_converter,
    )

    return _temporal_client


async def start_evaluation_workflow(
    trace_id: str,
    mode: str,
    question: str,
    contexts: list[str],
    answer: str,
) -> str:
    """
    Start an evaluation workflow (fire-and-forget).

    Parameters
    ----------
    trace_id : str
        The trace ID for Langfuse.
    mode : str
        The mode ("research" or "dialogue").
    question : str
        The user's question.
    contexts : list[str]
        Retrieved context documents.
    answer : str
        The generated answer.

    Returns
    -------
    str
        The workflow ID.
    """
    from pydantic import BaseModel

    # Define input model inline to avoid circular imports
    class EvaluationInput(BaseModel):
        """Input for EvaluationWorkflow."""

        trace_id: str
        mode: str
        question: str
        contexts: list[str]
        answer: str

        class Config:
            """Pydantic config for camelCase serialization."""

            populate_by_name = True

    client = await get_temporal_client()

    workflow_id = f"evaluation-{mode}-{uuid.uuid4().hex[:8]}"

    input_data = EvaluationInput(
        trace_id=trace_id,
        mode=mode,
        question=question,
        contexts=contexts,
        answer=answer,
    )

    # Start workflow (fire-and-forget, don't wait for result)
    await client.start_workflow(
        "EvaluationWorkflow",
        input_data,
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    logger.info(
        "Started evaluation workflow",
        workflow_id=workflow_id,
        trace_id=trace_id,
        mode=mode,
    )

    return workflow_id
