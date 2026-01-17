"""CLI for testing agents and API."""

import argparse
import asyncio
import sys
from typing import cast

import httpx
from langchain_core.messages import AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from buun_curator_agent.config import settings
from buun_curator_agent.graphs.research import create_research_graph
from buun_curator_agent.models.research import ResearchState, SearchMode

DEFAULT_BASE_URL = "http://buun-curator-agent.buun-curator:8000"


async def run_dialogue(message: str, entry_context: str | None = None) -> None:
    """
    Run dialogue mode directly (without API).

    Parameters
    ----------
    message : str
        User message.
    entry_context : str | None
        Optional entry context.
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(f"\nDialogue Query: {message}")
    if entry_context:
        print(f"Entry Context: {entry_context[:100]}...")
    print("-" * 60)

    # Build system prompt
    system_prompt = (
        "You are a helpful AI assistant for a feed reader application. "
        "Help users understand and analyze entries they are reading."
    )
    if entry_context:
        system_prompt += (
            f"\n\nThe user is currently reading the following entry:\n\n{entry_context}"
        )

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=message),
    ]

    # Stream LLM response
    llm = ChatOpenAI(
        model=settings.research_model,
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url or None,
        streaming=True,
    )

    print("\nResponse:")
    async for chunk in llm.astream(messages):
        if isinstance(chunk, AIMessageChunk) and chunk.content:
            print(chunk.content, end="", flush=True)
    print()


async def run_research(query: str, mode: SearchMode) -> None:
    """
    Run research graph directly (without API).

    Parameters
    ----------
    query : str
        Research query.
    mode : SearchMode
        Search mode to use.
    """
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(f"\nResearch Query: {query}")
    print(f"Search Mode: {mode}")
    print("-" * 60)

    initial_state: ResearchState = {
        "query": query,
        "entry_context": None,
        "search_mode": mode,
        "plan": None,
        "retrieved_docs": [],
        "final_answer": "",
        "iteration": 0,
        "needs_more_info": False,
        "trace_id": None,
        "session_id": None,
    }

    graph = create_research_graph()
    result = await graph.ainvoke(initial_state)

    final_answer = result.get("final_answer", "")
    retrieved_docs = result.get("retrieved_docs", [])
    plan = result.get("plan")

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if plan:
        print("\nPlan:")
        print(f"  Sub-queries: {plan.sub_queries}")
        print(f"  Sources: {plan.sources}")
        print(f"  Reasoning: {plan.reasoning}")

    print(f"\nRetrieved Documents: {len(retrieved_docs)}")
    for i, doc in enumerate(retrieved_docs, 1):
        score_str = f" (score: {doc.relevance_score:.3f})" if doc.relevance_score else ""
        print(f"  [{i}] [{doc.source}] {doc.title}{score_str}")

    print(f"\nFinal Answer:\n{final_answer}")


def api_chat(base_url: str, message: str, stream: bool = False) -> None:
    """
    Test chat API endpoint.

    Parameters
    ----------
    base_url : str
        Base URL of the agent service.
    message : str
        Message to send.
    stream : bool
        Whether to use streaming endpoint.
    """
    if stream:
        url = f"{base_url}/chat/stream"
        with httpx.stream("POST", url, json={"message": message}, timeout=60.0) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        print()
                        break
                    import json

                    chunk = json.loads(data)
                    if chunk.get("type") == "text":
                        print(chunk.get("content", ""), end="", flush=True)
    else:
        url = f"{base_url}/chat"
        response = httpx.post(url, json={"message": message}, timeout=60.0)
        response.raise_for_status()
        result = response.json()
        print(result.get("message", ""))


def api_health(base_url: str) -> None:
    """
    Test health API endpoint.

    Parameters
    ----------
    base_url : str
        Base URL of the agent service.
    """
    url = f"{base_url}/health"
    response = httpx.get(url, timeout=10.0)
    response.raise_for_status()
    print(response.json())


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Agent CLI for testing agents and API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run dialogue agent directly
  agent-cli dialogue "What is LangGraph?"

  # Run research agent with specific mode
  agent-cli research "LangGraphとは何か？" --mode embedding

  # Test API endpoints
  agent-cli api chat "Hello"
  agent-cli api health
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # dialogue command - run dialogue agent directly
    dialogue_parser = subparsers.add_parser(
        "dialogue",
        help="Run dialogue agent directly (simple LLM chat)",
    )
    dialogue_parser.add_argument("message", help="User message")
    dialogue_parser.add_argument(
        "--context",
        "-c",
        help="Entry context (entry content)",
    )

    # research command - run research agent directly
    research_parser = subparsers.add_parser(
        "research",
        help="Run research agent directly (LangGraph workflow)",
    )
    research_parser.add_argument("query", help="Research query")
    research_parser.add_argument(
        "--mode",
        "-m",
        choices=["planner", "meilisearch", "embedding", "hybrid"],
        default="planner",
        help="Search mode (default: planner)",
    )

    # api command - test API endpoints
    api_parser = subparsers.add_parser(
        "api",
        help="Test API endpoints",
    )
    api_parser.add_argument(
        "--base-url",
        "-u",
        default=DEFAULT_BASE_URL,
        help=f"Base URL of the agent service (default: {DEFAULT_BASE_URL})",
    )

    api_subparsers = api_parser.add_subparsers(dest="api_command", required=True)

    # api chat
    api_chat_parser = api_subparsers.add_parser("chat", help="Test /chat endpoint")
    api_chat_parser.add_argument("message", help="Message to send")
    api_chat_parser.add_argument("--stream", "-s", action="store_true", help="Use streaming")

    # api health
    api_subparsers.add_parser("health", help="Test /health endpoint")

    args = parser.parse_args()

    try:
        if args.command == "dialogue":
            asyncio.run(run_dialogue(args.message, args.context))
        elif args.command == "research":
            asyncio.run(run_research(args.query, cast(SearchMode, args.mode)))
        elif args.command == "api":
            if args.api_command == "chat":
                api_chat(args.base_url, args.message, args.stream)
            elif args.api_command == "health":
                api_health(args.base_url)
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError as e:
        print(f"Connection error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
