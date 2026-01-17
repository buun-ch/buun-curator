#!/usr/bin/env python3
"""
Debug script to check Graphiti data in FalkorDB.

Usage:
    cd worker
    op run --env-file=.env.op -- uv run python scripts/check_graphiti_data.py <entry_id>
"""

import asyncio
import os
import sys


async def check_graphiti_data(entry_id: str) -> None:
    """Check what data exists in FalkorDB for a Graphiti session."""
    from graphiti_core.driver.falkordb_driver import FalkorDriver

    graph_name = f"buun_curator_graphiti_{entry_id}"
    print(f"\n=== Checking FalkorDB graph: {graph_name} ===\n")

    driver = FalkorDriver(
        host=os.getenv("FALKORDB_HOST", "localhost"),
        port=int(os.getenv("FALKORDB_PORT", "6379")),
        username=os.getenv("FALKORDB_USERNAME") or None,
        password=os.getenv("FALKORDB_PASSWORD") or None,
        database=graph_name,
    )

    # Check total node count
    print("1. Total node count:")
    result = await driver.execute_query("MATCH (n) RETURN count(n) as cnt")
    print(f"   Result: {result}")

    # Check node labels
    print("\n2. Node labels:")
    result = await driver.execute_query("MATCH (n) RETURN DISTINCT labels(n) as labels")
    print(f"   Result: {result}")

    # Check entity nodes
    print("\n3. Entity nodes (first 5):")
    result = await driver.execute_query("MATCH (n:Entity) RETURN n LIMIT 5")
    print(f"   Count: {len(result) if result else 0}")
    for r in result or []:
        print(f"   - {r}")

    # Check episode nodes
    print("\n4. Episode nodes:")
    result = await driver.execute_query("MATCH (n:Episodic) RETURN n LIMIT 5")
    print(f"   Count: {len(result) if result else 0}")
    for r in result or []:
        print(f"   - {r}")

    # Check edges
    print("\n5. Edges (first 5):")
    result = await driver.execute_query(
        "MATCH (a)-[r]->(b) RETURN type(r) as rel_type, a.name, b.name LIMIT 5"
    )
    print(f"   Count: {len(result) if result else 0}")
    for r in result or []:
        print(f"   - {r}")

    # Check group_ids on nodes
    print("\n6. Group IDs on entities:")
    result = await driver.execute_query("MATCH (n:Entity) RETURN n.group_id as group_id LIMIT 5")
    print(f"   Result: {result}")

    # Check group_ids on edges
    print("\n7. Group IDs on edges:")
    result = await driver.execute_query("MATCH ()-[r]->() RETURN r.group_id as group_id LIMIT 5")
    print(f"   Result: {result}")

    await driver.close()
    print("\n=== Done ===")


def main() -> None:
    """Entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_graphiti_data.py <entry_id>")
        sys.exit(1)

    entry_id = sys.argv[1]
    asyncio.run(check_graphiti_data(entry_id))


if __name__ == "__main__":
    main()
