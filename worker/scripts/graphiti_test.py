#!/usr/bin/env python3
"""
Test script for GraphitiSession.

Usage:
    # From worker/ directory with port-forwarding to FalkorDB:
    kubectl port-forward svc/falkordb 6379:6379 -n falkordb

    # Run the test:
    op run --env-file=.env.op -- uv run python scripts/test_graphiti.py

Environment variables required:
    - FALKORDB_HOST (default: localhost)
    - FALKORDB_PORT (default: 6379)
    - FALKORDB_USERNAME (optional)
    - FALKORDB_PASSWORD (optional)
    - OPENAI_API_KEY or OPENAI_BASE_URL for LiteLLM proxy
"""

import asyncio
import logging
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def check_graphiti_session() -> bool:
    """
    Test GraphitiSession with FalkorDB.

    Returns
    -------
    bool
        True if all tests pass.
    """
    from buun_curator.graphiti import GraphitiSession

    test_entry_id = "test_graphiti_001"

    logger.info("=" * 60)
    logger.info("Starting GraphitiSession Test")
    logger.info("=" * 60)

    # Check environment
    logger.info(f"FALKORDB_HOST: {os.getenv('FALKORDB_HOST', 'localhost')}")
    logger.info(f"FALKORDB_PORT: {os.getenv('FALKORDB_PORT', '6379')}")
    logger.info(f"OPENAI_BASE_URL: {os.getenv('OPENAI_BASE_URL', 'not set')}")

    session = None
    try:
        # 1. Create session
        logger.info("\n--- Step 1: Create session ---")
        session = await GraphitiSession.create(test_entry_id)
        logger.info(f"Session created: graph_name={session.graph_name}")

        # 2. Add content (this should build graph incrementally)
        logger.info("\n--- Step 2: Add content ---")

        content1 = """
# Buun Curator

Buun Curator is an AI-powered feed reader application.

## Features

- Multi-panel UI with subscription sidebar, entry list, and content viewer
- AI assistant for research and summarization
- Support for RSS/Atom feeds and Reddit integration

## Tech Stack

- Frontend: Next.js, React, TypeScript
- Backend: Temporal workflows, Python worker
- Database: PostgreSQL, FalkorDB
"""

        logger.info("Adding content...")
        await session.add_content(
            content=content1,
            source_type="readme",
            metadata={"title": "Buun Curator README"},
        )
        logger.info("Content added successfully!")

        # Wait a moment for async operations to complete
        await asyncio.sleep(2)

        # 3. Search the graph
        logger.info("\n--- Step 3: Search graph ---")

        query = "What is Buun Curator?"
        logger.info(f"Query: {query}")
        results = await session.search_graph(query, top_k=5)
        logger.info(f"Results: {len(results)}")
        for i, result in enumerate(results):
            content_preview = result.content[:100] if result.content else "(empty)"
            logger.info(f"  [{i + 1}] {result.source_type}: {content_preview}...")

        # 4. Close session
        logger.info("\n--- Step 4: Close session ---")
        await session.close()
        session = None
        logger.info("Session closed")

        # Wait a moment for connections to close properly
        await asyncio.sleep(1)

        # 5. Clean up
        logger.info("\n--- Step 5: Clean up ---")
        await GraphitiSession.reset(test_entry_id)
        logger.info("Test data cleaned up")

        logger.info("\n" + "=" * 60)
        logger.info("All tests passed!")
        logger.info("=" * 60)
        return True

    except Exception as e:
        logger.exception(f"Test failed: {e}")
        # Try to clean up
        import contextlib

        if session:
            with contextlib.suppress(Exception):
                await session.close()

        with contextlib.suppress(Exception):
            await GraphitiSession.reset(test_entry_id)
        return False


async def check_connection_only() -> bool:
    """
    Test FalkorDB connection without full GraphitiSession.

    Returns
    -------
    bool
        True if connection succeeds.
    """
    logger.info("Testing FalkorDB connection...")

    try:
        from graphiti_core.driver.falkordb_driver import FalkorDriver

        host = os.getenv("FALKORDB_HOST", "localhost")
        port = int(os.getenv("FALKORDB_PORT", "6379"))
        username = os.getenv("FALKORDB_USERNAME") or None
        password = os.getenv("FALKORDB_PASSWORD") or None

        logger.info(f"Connecting to FalkorDB at {host}:{port}")

        driver = FalkorDriver(
            host=host,
            port=port,
            username=username,
            password=password,
            database="buun_curator_test_connection",
        )

        # Try a simple query
        result = await driver.execute_query("RETURN 1 as test")
        logger.info(f"Connection successful! Result: {result}")

        await driver.close()
        return True

    except Exception as e:
        logger.exception(f"Connection failed: {e}")
        return False


def main() -> int:
    """Run tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Test GraphitiSession")
    parser.add_argument(
        "--connection-only",
        action="store_true",
        help="Only test FalkorDB connection",
    )
    args = parser.parse_args()

    if args.connection_only:
        success = asyncio.run(check_connection_only())
    else:
        success = asyncio.run(check_graphiti_session())

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
