"""Tests for research LangGraph."""

from buun_curator_agent.graphs.research import create_research_graph, should_continue
from buun_curator_agent.models.research import ResearchState


class TestShouldContinue:
    """Tests for the should_continue conditional function."""

    def test_end_when_not_needs_more_info(self) -> None:
        """End when needs_more_info is False."""
        state: ResearchState = {
            "query": "test",
            "entry_context": None,
            "search_mode": None,
            "plan": None,
            "retrieved_docs": [],
            "final_answer": "Answer",
            "iteration": 1,
            "needs_more_info": False,
            "trace_id": "test-trace-id",
            "session_id": None,
        }
        assert should_continue(state) == "end"

    def test_continue_when_needs_more_info(self) -> None:
        """Continue when needs_more_info is True and under max iterations."""
        state: ResearchState = {
            "query": "test",
            "entry_context": None,
            "search_mode": None,
            "plan": None,
            "retrieved_docs": [],
            "final_answer": "",
            "iteration": 1,
            "needs_more_info": True,
            "trace_id": "test-trace-id",
            "session_id": None,
        }
        assert should_continue(state) == "continue"

    def test_end_at_max_iterations(self) -> None:
        """End when max iterations reached even if needs_more_info."""
        state: ResearchState = {
            "query": "test",
            "entry_context": None,
            "search_mode": None,
            "plan": None,
            "retrieved_docs": [],
            "final_answer": "",
            "iteration": 3,
            "needs_more_info": True,
            "trace_id": "test-trace-id",
            "session_id": None,
        }
        assert should_continue(state) == "end"


class TestCreateResearchGraph:
    """Tests for research graph creation."""

    def test_graph_creation(self) -> None:
        """Graph can be created successfully."""
        graph = create_research_graph()
        assert graph is not None

    def test_graph_has_nodes(self) -> None:
        """Graph contains expected nodes."""
        graph = create_research_graph()
        # CompiledStateGraph exposes nodes via get_graph()
        graph_def = graph.get_graph()
        node_names = [node.name for node in graph_def.nodes.values()]
        assert "planner" in node_names
        assert "retriever" in node_names
        assert "writer" in node_names
