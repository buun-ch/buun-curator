"""Research mode agent implementation using LangGraph."""

import uuid
from collections.abc import AsyncGenerator
from typing import Any

from ag_ui.core import (
    EventType,
    RunAgentInput,
    StateSnapshotEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)
from ag_ui.encoder import EventEncoder
from langchain_core.messages import HumanMessage

from buun_curator_agent.agents.common import build_messages_from_input, get_entry_context
from buun_curator_agent.config import settings
from buun_curator_agent.graphs.research import create_research_graph
from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import ResearchState

logger = get_logger(__name__)


def _get_last_user_message(input_data: RunAgentInput) -> str | None:
    """Extract the last user message from input."""
    messages = build_messages_from_input(input_data)
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            return str(msg.content)
    return None


def _create_step(
    step_type: str,
    status: str,
    iteration: int,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a research step object."""
    return {
        "id": f"{step_type}-{iteration}-{uuid.uuid4().hex[:8]}",
        "type": step_type,
        "status": status,
        "iteration": iteration,
        "data": data or {},
    }


async def run_research(
    input_data: RunAgentInput,
    encoder: EventEncoder,
    message_id: str,
    trace_id: str,
    session_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run research mode using LangGraph multi-agent workflow.

    The workflow consists of:
    1. Planner: Analyze query and create search plan
    2. Retriever: Execute searches based on plan
    3. Writer: Generate final answer from retrieved documents

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
    # Get the user query
    query = _get_last_user_message(input_data)
    if not query:
        logger.warning("No user message found in input")
        return

    # Get entry context
    entry_context = await get_entry_context(input_data)

    logger.info("Starting research", query=query[:50], trace_id=trace_id)

    # Emit text message start
    yield encoder.encode(
        TextMessageStartEvent(
            type=EventType.TEXT_MESSAGE_START,
            message_id=message_id,
            role="assistant",
        )
    )

    # Create initial state
    initial_state: ResearchState = {
        "query": query,
        "entry_context": entry_context,
        "search_mode": None,  # Use default from config
        "plan": None,
        "retrieved_docs": [],
        "final_answer": "",
        "iteration": 0,
        "needs_more_info": False,
        "trace_id": trace_id,
        "session_id": session_id,
    }

    # Create and run the graph
    graph = create_research_graph()

    # Track research steps for UI
    research_steps: list[dict[str, Any]] = []
    current_iteration = 0

    # Track data for evaluation
    retrieved_docs_for_eval: list[str] = []
    final_answer_for_eval = ""

    def emit_steps() -> str:
        """Emit current research steps as state snapshot event."""
        logger.debug("Emitting STATE_SNAPSHOT", step_count=len(research_steps))
        encoded = encoder.encode(
            StateSnapshotEvent(
                type=EventType.STATE_SNAPSHOT,
                snapshot={"researchSteps": research_steps},
            )
        )
        logger.debug("Encoded STATE_SNAPSHOT event", encoded_preview=encoded[:200])
        return encoded

    try:
        # Stream events from the graph
        async for event in graph.astream_events(initial_state, version="v2"):
            event_kind = event.get("event")
            event_name = event.get("name", "")

            # Node started - add in_progress step
            if event_kind == "on_chain_start":
                if event_name == "planner":
                    # Get iteration from input if available
                    input_data_event = event.get("data", {}).get("input", {})
                    current_iteration = input_data_event.get("iteration", 0) + 1

                    research_steps.append(
                        _create_step(
                            "planning",
                            "in_progress",
                            current_iteration,
                            {"message": "Analyzing query and creating search plan..."},
                        )
                    )
                    yield emit_steps()

                elif event_name == "retriever":
                    research_steps.append(
                        _create_step(
                            "retrieval",
                            "in_progress",
                            current_iteration,
                            {"message": "Searching for relevant information..."},
                        )
                    )
                    yield emit_steps()

                elif event_name == "writer":
                    research_steps.append(
                        _create_step(
                            "writing",
                            "in_progress",
                            current_iteration,
                            {"message": "Synthesizing response..."},
                        )
                    )
                    yield emit_steps()

            # Node completed - update step with results
            elif event_kind == "on_chain_end":
                output = event.get("data", {}).get("output", {})

                if event_name == "planner":
                    plan = output.get("plan")
                    if plan and research_steps:
                        # Update the last planning step
                        for step in reversed(research_steps):
                            if step["type"] == "planning" and step["status"] == "in_progress":
                                step["status"] = "complete"
                                step["data"] = {
                                    "subQueries": plan.sub_queries,
                                    "sources": plan.sources,
                                    "reasoning": plan.reasoning,
                                }
                                break
                        yield emit_steps()

                elif event_name == "retriever":
                    docs = output.get("retrieved_docs", [])
                    # Store document content for evaluation
                    retrieved_docs_for_eval.extend(
                        [doc.content for doc in docs if hasattr(doc, "content")]
                    )
                    if research_steps:
                        # Update the last retrieval step
                        for step in reversed(research_steps):
                            if step["type"] == "retrieval" and step["status"] == "in_progress":
                                step["status"] = "complete"
                                step["data"] = {
                                    "documentsFound": len(docs),
                                    "documents": [
                                        {
                                            "id": doc.id,
                                            "title": doc.title,
                                            "source": doc.source,
                                            "score": doc.relevance_score,
                                        }
                                        for doc in docs[:10]  # Limit to 10 for UI
                                    ],
                                }
                                break
                        yield emit_steps()

                elif event_name == "writer":
                    final_answer = output.get("final_answer", "")
                    needs_more = output.get("needs_more_info", False)

                    if research_steps:
                        # Update the last writing step
                        for step in reversed(research_steps):
                            if step["type"] == "writing" and step["status"] == "in_progress":
                                step["status"] = "complete"
                                step["data"] = {
                                    "message": "Response generated",
                                    "needsMoreInfo": needs_more,
                                }
                                break
                        yield emit_steps()

                    if final_answer and not needs_more:
                        # Store for evaluation
                        final_answer_for_eval = final_answer  # noqa: F841 - used outside loop

                        # Stream the answer in chunks for better UX
                        chunk_size = 50
                        for i in range(0, len(final_answer), chunk_size):
                            chunk = final_answer[i : i + chunk_size]
                            yield encoder.encode(
                                TextMessageContentEvent(
                                    type=EventType.TEXT_MESSAGE_CONTENT,
                                    message_id=message_id,
                                    delta=chunk,
                                )
                            )

    except Exception as e:
        logger.error(
            f"Research failed: {e}",
            trace_id=trace_id,
            error_type=type(e).__name__,
        )
        # Mark any in_progress steps as error
        for step in research_steps:
            if step["status"] == "in_progress":
                step["status"] = "error"
                step["data"]["message"] = f"Failed: {e}"
        # Add error step
        research_steps.append(
            _create_step(
                "error",
                "error",
                current_iteration,
                {"message": str(e)},
            )
        )
        yield emit_steps()

        # Emit error message
        yield encoder.encode(
            TextMessageContentEvent(
                type=EventType.TEXT_MESSAGE_CONTENT,
                message_id=message_id,
                delta=f"An error occurred during research: {e}",
            )
        )

    # Start RAGAS evaluation workflow if enabled
    if settings.ai_evaluation_enabled and final_answer_for_eval and retrieved_docs_for_eval:
        try:
            from buun_curator_agent.temporal import start_evaluation_workflow

            workflow_id = await start_evaluation_workflow(
                trace_id=trace_id,
                mode="research",
                question=query,
                contexts=retrieved_docs_for_eval,
                answer=final_answer_for_eval,
            )
            logger.info(
                "Started RAGAS evaluation workflow",
                workflow_id=workflow_id,
                trace_id=trace_id,
                mode="research",
            )
        except Exception as e:
            logger.error(
                f"Failed to start RAGAS evaluation workflow: {e}",
                trace_id=trace_id,
                mode="research",
                error_type=type(e).__name__,
            )

    # Emit text message end
    yield encoder.encode(
        TextMessageEndEvent(
            type=EventType.TEXT_MESSAGE_END,
            message_id=message_id,
        )
    )
