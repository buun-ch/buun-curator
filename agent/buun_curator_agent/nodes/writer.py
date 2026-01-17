"""Writer node for Deep Research LangGraph."""

from typing import cast

from langchain_core.prompts import ChatPromptTemplate

from buun_curator_agent.logging import get_logger
from buun_curator_agent.models.research import ResearchAnswer, ResearchState
from buun_curator_agent.prompts import load_prompt
from buun_curator_agent.utils.llm import create_research_llm

logger = get_logger(__name__)

WRITER_SYSTEM_PROMPT = load_prompt("writer")


def _format_retrieved_docs(docs: list) -> str:
    """Format retrieved documents for the prompt."""
    if not docs:
        return "No documents retrieved."

    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(f"[{i}] {doc.title}")
        if doc.content:
            # Truncate long content
            content = doc.content[:500] + "..." if len(doc.content) > 500 else doc.content
            parts.append(f"    {content}")
        parts.append("")

    return "\n".join(parts)


async def writer_node(state: ResearchState) -> ResearchState:
    """
    Writer node: generate final answer from retrieved documents.

    Parameters
    ----------
    state : ResearchState
        Current graph state with retrieved documents.

    Returns
    -------
    ResearchState
        Updated state with final answer.
    """
    query = state["query"]
    entry_context = state.get("entry_context") or "No entry context provided."
    retrieved_docs = state.get("retrieved_docs", [])
    iteration = state.get("iteration", 1)

    logger.info(
        "Generating answer",
        doc_count=len(retrieved_docs),
        iteration=iteration,
    )

    trace_id = state.get("trace_id")
    session_id = state.get("session_id")
    llm = create_research_llm(
        trace_id=trace_id,
        generation_name="chat-research-writer",
        session_id=session_id,
        temperature=0.3,
    )
    structured_llm = llm.with_structured_output(ResearchAnswer)

    prompt = ChatPromptTemplate.from_messages([
        ("system", WRITER_SYSTEM_PROMPT),
        ("human", "{query}"),
    ])

    chain = prompt | structured_llm
    result = await chain.ainvoke({
        "query": query,
        "entry_context": entry_context,
        "retrieved_docs": _format_retrieved_docs(retrieved_docs),
    })
    answer = cast(ResearchAnswer, result)

    logger.info(
        "Generated answer",
        answer_type=answer.answer_type,
        confidence=answer.confidence,
        needs_more_info=answer.needs_more_info,
    )

    return ResearchState(
        query=state["query"],
        entry_context=state["entry_context"],
        search_mode=state.get("search_mode"),
        plan=state.get("plan"),
        retrieved_docs=retrieved_docs,
        final_answer=answer.answer,
        iteration=state.get("iteration", 1),
        needs_more_info=answer.needs_more_info,
        trace_id=state.get("trace_id"),
        session_id=state.get("session_id"),
    )
