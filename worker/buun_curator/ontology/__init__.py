"""
Ontology module for Buun Curator.

Provides the custom ontology for use with Cognee's knowledge graph.
"""

from pathlib import Path

# Path to the ontology file
ONTOLOGY_FILE = Path(__file__).parent / "buun_curator_ontology.ttl"


def get_ontology_path() -> str:
    """
    Get the absolute path to the Buun Curator ontology file.

    Returns
    -------
    str
        Absolute path to buun_curator_ontology.ttl.
    """
    return str(ONTOLOGY_FILE.resolve())
