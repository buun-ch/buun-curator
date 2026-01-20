"""AG-UI protocol endpoint for CopilotKit integration."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal

from ag_ui.core import (
    CustomEvent,
    EventType,
    RunAgentInput,
    RunFinishedEvent,
    RunStartedEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ulid import ULID

from buun_curator_agent.agents import run_dialogue, run_research
from buun_curator_agent.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()

ChatMode = Literal["dialogue", "research"]


def _get_info() -> dict[str, Any]:
    """Return agent information for CopilotKit discovery."""
    return {
        "agents": {
            "default": {
                "name": "default",
                "description": "AI assistant for analyzing feed entries",
            }
        },
        "actions": [],
        "version": "1.0",
    }


@router.get("/info")
async def info_get() -> dict[str, Any]:
    """
    Return agent information for CopilotKit discovery (GET).

    Returns
    -------
    dict[str, Any]
        Agent information including available agents and version.
    """
    return _get_info()


@router.post("/info")
async def info_post() -> dict[str, Any]:
    """
    Return agent information for CopilotKit discovery (POST).

    Returns
    -------
    dict[str, Any]
        Agent information including available agents and version.
    """
    return _get_info()


async def run_agent(input_data: RunAgentInput) -> AsyncGenerator[str, None]:
    """
    Run the agent and yield AG-UI events.

    Dispatches to mode-specific handlers based on the mode property.

    Parameters
    ----------
    input_data : RunAgentInput
        Input data from the client including messages and properties.

    Yields
    ------
    str
        SSE-encoded events.
    """
    encoder = EventEncoder()
    run_id = str(ULID())
    thread_id = input_data.thread_id or str(ULID())
    message_id = str(ULID())
    # 32-char hex format for Langfuse SDK v3 compatibility
    trace_id = uuid.uuid4().hex

    # Get mode and session_id from forwarded properties
    mode: ChatMode = "dialogue"
    session_id: str | None = None
    if input_data.forwarded_props:
        mode_value = input_data.forwarded_props.get("mode")
        if mode_value in ("dialogue", "research"):
            mode = mode_value
        session_id = input_data.forwarded_props.get("sessionId")

    logger.info(
        "Agent run started",
        run_id=run_id,
        mode=mode,
        trace_id=trace_id,
        session_id=session_id,
    )

    # Emit run started event
    yield encoder.encode(
        RunStartedEvent(
            type=EventType.RUN_STARTED,
            thread_id=thread_id,
            run_id=run_id,
        )
    )

    try:
        # Dispatch to mode-specific handler
        if mode == "research":
            async for event in run_research(input_data, encoder, message_id, trace_id, session_id):
                yield event
        else:
            async for event in run_dialogue(input_data, encoder, message_id, trace_id, session_id):
                yield event

    except Exception as e:
        logger.error(
            f"Agent run failed: {e}",
            run_id=run_id,
            trace_id=trace_id,
            error_type=type(e).__name__,
        )
        # Emit error as a custom event
        yield encoder.encode(
            CustomEvent(
                type=EventType.CUSTOM,
                name="error",
                value={"message": str(e)},
            )
        )

    # Always emit run finished event
    yield encoder.encode(
        RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            thread_id=thread_id,
            run_id=run_id,
        )
    )


@router.post("")
async def ag_ui_endpoint(input_data: RunAgentInput) -> StreamingResponse:
    """
    AG-UI protocol endpoint for CopilotKit.

    Parameters
    ----------
    input_data : RunAgentInput
        Input data from CopilotKit client.

    Returns
    -------
    StreamingResponse
        Server-sent events stream with AG-UI events.
    """
    return StreamingResponse(
        run_agent(input_data),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
