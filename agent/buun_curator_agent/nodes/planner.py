"""Planner node for Deep Research LangGraph."""

from typing import cast

from langchain_core.prompts import ChatPromptTemplate

from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import ResearchState, SearchPlan
from buun_curator_agent.prompts import load_prompt
from buun_curator_agent.utils.llm import create_research_llm

logger = get_logger(__name__)

PLANNER_SYSTEM_PROMPT = load_prompt("planner")


async def planner_node(state: ResearchState) -> ResearchState:
    """
    Planner node: analyze query and create search plan.

    Parameters
    ----------
    state : ResearchState
        Current graph state.

    Returns
    -------
    ResearchState
        Updated state with search plan.
    """
    query = state["query"]
    entry_context = state.get("entry_context") or "No entry context provided."
    iteration = state.get("iteration", 0)

    logger.info("Processing query for planning", query=query[:50], iteration=iteration)

    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    llm = create_research_llm(
        trace_id=trace_id,
        generation_name="chat-research-planner",
        session_id=session_id,
    )
    structured_llm = llm.with_structured_output(SearchPlan)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", "{query}"),
        ]
    )

    chain = prompt | structured_llm
    result = await chain.ainvoke(
        {
            "query": query,
            "entry_context": entry_context,
        }
    )
    plan = cast(SearchPlan, result)

    logger.info(
        "Created search plan",
        query_count=len(plan.sub_queries),
        sources=plan.sources,
    )

    return ResearchState(
        query=state["query"],
        entry_context=state["entry_context"],
        search_mode=state.get("search_mode"),
        plan=plan,
        retrieved_docs=state.get("retrieved_docs", []),
        final_answer=state.get("final_answer", ""),
        iteration=iteration + 1,
        needs_more_info=state.get("needs_more_info", False),
        trace_id=state.get("trace_id"),
        session_id=state.get("session_id"),
    )
