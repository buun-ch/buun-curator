"""Dialogue mode agent implementation."""

from collections.abc import AsyncGenerator

from ag_ui.core import (
    EventType,
    RunAgentInput,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from buun_curator_agent.agents.common import build_messages_from_input, get_entry_context
from buun_curator_agent.config import settings
from buun_curator_agent.logging import get_logger

logger = get_logger(__name__)


def _get_last_user_message(input_data: RunAgentInput) -> str | None:
    """Extract the last user message from input."""
    messages = build_messages_from_input(input_data)
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return None


async def run_dialogue(
    input_data: RunAgentInput,
    encoder: EventEncoder,
    message_id: str,
    trace_id: str,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run dialogue mode: simple chat with LLM.

    Parameters
    ----------
    input_data : RunAgentInput
        Input data from the client.
    encoder : EventEncoder
        AG-UI event encoder.
    message_id : str
        Message ID for this response.
    trace_id : str
        Trace ID for Langfuse.
    session_id : str | None, optional
        Session ID for Langfuse session grouping (default: None).

    Yields
    ------
    str
        SSE-encoded events.
    """
    # Build messages
    entry_context = await get_entry_context(input_data)

    system_prompt = (
        "You are a helpful AI assistant for a feed reader application. "
        "Help users understand and analyze entries they are reading."
    )
    if entry_context:
        system_prompt += (
            f"\n\nThe user is currently reading the following entry:\n\n{entry_context}"
        )

    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    messages.extend(build_messages_from_input(input_data))

    # Check if we have user messages
    if not any(isinstance(m, HumanMessage) for m in messages):
        return

    # Emit text message start
    yield encoder.encode(
        TextMessageStartEvent(
            type=EventType.TEXT_MESSAGE_START,
            message_id=message_id,
            role="assistant",
        )
    )

    # Get the user query for evaluation
    query = _get_last_user_message(input_data)

    # Build metadata for Langfuse tracing
    # See: https://docs.litellm.ai/docs/observability/langfuse_integration
    metadata: dict[str, str] = {
        "trace_id": trace_id,
        "trace_name": "chat-dialogue",
        "generation_name": "chat-dialogue",
    }
    if session_id:
        metadata["session_id"] = session_id

    # Stream LLM response
    llm = ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        streaming=True,
        extra_body={"metadata": metadata},
    )

    # Collect answer for evaluation
    answer_chunks: list[str] = []

    async for chunk in llm.astream(messages):
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            content = str(chunk.content)
            answer_chunks.append(content)
            yield encoder.encode(
                TextMessageContentEvent(
                    type=EventType.TEXT_MESSAGE_CONTENT,
                    message_id=message_id,
                    delta=content,
                )
            )

    # Start RAGAS evaluation workflow if enabled
    # Using entry_context as the context for evaluation
    final_answer = "".join(answer_chunks)
    if settings.ai_evaluation_enabled and query and entry_context and final_answer:
        try:
            from buun_curator_agent.temporal import start_evaluation_workflow

            workflow_id = await start_evaluation_workflow(
                trace_id=trace_id,
                mode="dialogue",
                question=query,
                contexts=[entry_context],
                answer=final_answer,
            )
            logger.info(
                "Started RAGAS evaluation workflow for dialogue",
                workflow_id=workflow_id,
                trace_id=trace_id,
            )
        except Exception:
            logger.exception(
                "Failed to start RAGAS evaluation workflow for dialogue",
                trace_id=trace_id,
            )

    # Emit text message end
    yield encoder.encode(
        TextMessageEndEvent(
            type=EventType.TEXT_MESSAGE_END,
            message_id=message_id,
        )
    )
