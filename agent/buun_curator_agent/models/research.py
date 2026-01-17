"""Pydantic models for Deep Research LangGraph."""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field

# Search mode determines how sources are selected
SearchMode = Literal["planner", "meilisearch", "embedding", "hybrid"]

# Available search sources
SearchSource = Literal["meilisearch", "embedding"]


class SearchPlan(BaseModel):
    """Planner output: search strategy for the query."""

    sub_queries: list[str] = Field(
        description="List of sub-queries to search for. "
        "Can be the original query or decomposed queries."
    )
    sources: list[SearchSource] = Field(
        default=["meilisearch"],
        description="Sources to search: meilisearch (keyword), embedding (semantic).",
    )
    reasoning: str = Field(
        description="Brief explanation of the search strategy."
    )


class RetrievedDoc(BaseModel):
    """A single retrieved document from search."""

    source: str = Field(description="Source of the document (e.g., 'meilisearch')")
    id: str = Field(description="Document ID")
    title: str = Field(description="Document title")
    content: str = Field(description="Document content or summary")
    url: str | None = Field(default=None, description="Document URL if available")
    relevance_score: float | None = Field(
        default=None, description="Relevance score from search"
    )


class SourceReference(BaseModel):
    """Reference to a source used in the answer."""

    id: str = Field(description="Document ID (e.g., '[1]')")
    title: str = Field(description="Document title")
    usage: str = Field(description="How this source was used in the answer")


class ResearchAnswer(BaseModel):
    """Writer output: the final research answer."""

    answer: str = Field(description="The research answer in Markdown format")
    answer_type: Literal["comparison", "explanation", "recommendation", "summary"] = (
        Field(description="Type of answer based on query analysis")
    )
    sources: list[SourceReference] = Field(
        default_factory=list, description="List of sources used in the answer"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score for the answer"
    )
    needs_more_info: bool = Field(
        default=False,
        description="Whether more information is needed to fully answer the query",
    )
    follow_ups: list[str] = Field(
        default_factory=list, description="Suggested follow-up questions"
    )


class ResearchState(TypedDict):
    """State for the Deep Research LangGraph."""

    # Input (required)
    query: str
    entry_context: str | None

    # Search mode (optional, default: "planner")
    search_mode: SearchMode | None

    # Planner output
    plan: SearchPlan | None

    # Retriever output
    retrieved_docs: list[RetrievedDoc]

    # Writer output
    final_answer: str

    # Control flow
    iteration: int
    needs_more_info: bool

    # Tracing (optional)
    trace_id: str | None
    session_id: str | None
