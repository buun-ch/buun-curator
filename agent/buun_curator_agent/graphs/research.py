"""Deep Research LangGraph definition."""

from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import ResearchState
from buun_curator_agent.nodes.planner import planner_node
from buun_curator_agent.nodes.retriever import retriever_node
from buun_curator_agent.nodes.writer import writer_node

logger = get_logger(__name__)

MAX_ITERATIONS = 3


def should_continue(state: ResearchState) -> Literal["continue", "end"]:
    """
    Determine whether to continue iterating or end.

    Parameters
    ----------
    state : ResearchState
        Current graph state.

    Returns
    -------
    Literal["continue", "end"]
        "continue" to run another iteration, "end" to finish.
    """
    needs_more_info = state.get("needs_more_info", False)
    iteration = state.get("iteration", 0)

    if not needs_more_info:
        logger.info("Research complete: sufficient information gathered", iteration=iteration)
        return "end"

    if iteration >= MAX_ITERATIONS:
        logger.info(
            "Research complete: max iterations reached",
            iteration=iteration,
            max_iterations=MAX_ITERATIONS,
        )
        return "end"

    logger.info(
        "Continuing research",
        current_iteration=iteration,
        next_iteration=iteration + 1,
    )
    return "continue"


def create_research_graph() -> CompiledStateGraph[ResearchState]:
    """
    Create the Deep Research LangGraph.

    Returns
    -------
    StateGraph
        Compiled LangGraph for deep research.

    Example
    -------
    >>> graph = create_research_graph()
    >>> result = await graph.ainvoke({
    ...     "query": "What is LangGraph?",
    ...     "entry_context": None,
    ...     "plan": None,
    ...     "retrieved_docs": [],
    ...     "final_answer": "",
    ...     "iteration": 0,
    ...     "needs_more_info": False,
    ... })
    >>> print(result["final_answer"])
    """
    # Create the graph
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("writer", writer_node)

    # Set entry point
    graph.set_entry_point("planner")

    # Add edges
    graph.add_edge("planner", "retriever")
    graph.add_edge("retriever", "writer")

    # Add conditional edge from writer
    graph.add_conditional_edges(
        "writer",
        should_continue,
        {
            "continue": "planner",
            "end": END,
        },
    )

    # Compile and return
    return graph.compile()
