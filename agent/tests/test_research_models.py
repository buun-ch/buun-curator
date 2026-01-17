"""Tests for research models."""

from buun_curator_agent.models.research import (
    ResearchAnswer,
    ResearchState,
    RetrievedDoc,
    SearchPlan,
    SourceReference,
)


class TestSearchPlan:
    """Tests for SearchPlan model."""

    def test_create_simple_plan(self) -> None:
        """Create a plan with single query."""
        plan = SearchPlan(
            sub_queries=["test query"],
            sources=["meilisearch"],
            reasoning="Simple test query",
        )
        assert len(plan.sub_queries) == 1
        assert plan.sub_queries[0] == "test query"
        assert "meilisearch" in plan.sources

    def test_create_multi_query_plan(self) -> None:
        """Create a plan with multiple sub-queries."""
        plan = SearchPlan(
            sub_queries=["query 1", "query 2", "query 3"],
            sources=["meilisearch"],
            reasoning="Complex query decomposed into parts",
        )
        assert len(plan.sub_queries) == 3


class TestRetrievedDoc:
    """Tests for RetrievedDoc model."""

    def test_create_doc(self) -> None:
        """Create a retrieved document."""
        doc = RetrievedDoc(
            source="meilisearch",
            id="doc-123",
            title="Test Document",
            content="This is test content",
            url="https://example.com/doc",
            relevance_score=0.95,
        )
        assert doc.id == "doc-123"
        assert doc.source == "meilisearch"
        assert doc.relevance_score == 0.95

    def test_create_doc_minimal(self) -> None:
        """Create a document with minimal fields."""
        doc = RetrievedDoc(
            source="meilisearch",
            id="doc-456",
            title="Minimal Doc",
            content="Content",
        )
        assert doc.url is None
        assert doc.relevance_score is None


class TestResearchAnswer:
    """Tests for ResearchAnswer model."""

    def test_create_answer(self) -> None:
        """Create a research answer."""
        answer = ResearchAnswer(
            answer="This is the answer.",
            answer_type="explanation",
            sources=[
                SourceReference(
                    id="[1]",
                    title="Source 1",
                    usage="Used for background information",
                )
            ],
            confidence=0.85,
            needs_more_info=False,
            follow_ups=["What about X?", "How does Y work?"],
        )
        assert answer.answer_type == "explanation"
        assert answer.confidence == 0.85
        assert len(answer.follow_ups) == 2
        assert len(answer.sources) == 1
        assert answer.sources[0].title == "Source 1"

    def test_answer_type_validation(self) -> None:
        """Validate answer_type is one of the allowed values."""
        for answer_type in ["comparison", "explanation", "recommendation", "summary"]:
            answer = ResearchAnswer(
                answer="Test",
                answer_type=answer_type,  # type: ignore[arg-type]
                confidence=0.5,
            )
            assert answer.answer_type == answer_type


class TestResearchState:
    """Tests for ResearchState TypedDict."""

    def test_create_initial_state(self) -> None:
        """Create initial research state."""
        state: ResearchState = {
            "query": "What is LangGraph?",
            "entry_context": None,
            "search_mode": None,
            "plan": None,
            "retrieved_docs": [],
            "final_answer": "",
            "iteration": 0,
            "needs_more_info": False,
            "trace_id": "test-trace-id",
            "session_id": None,
        }
        assert state["query"] == "What is LangGraph?"
        assert state["iteration"] == 0

    def test_create_state_with_context(self) -> None:
        """Create state with entry context."""
        state: ResearchState = {
            "query": "Summarize this",
            "entry_context": "Article about AI agents...",
            "search_mode": None,
            "plan": None,
            "retrieved_docs": [],
            "final_answer": "",
            "iteration": 0,
            "needs_more_info": False,
            "trace_id": "test-trace-id",
            "session_id": None,
        }
        assert state["entry_context"] == "Article about AI agents..."
