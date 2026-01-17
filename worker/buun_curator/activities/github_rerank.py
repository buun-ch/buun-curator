"""
GitHub repository re-ranking Activity.

Re-rank GitHub repository candidates using LLM to select the best match
based on entry context.
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr
from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    GitHubRepoInfo,
    RerankGitHubInput,
    RerankGitHubOutput,
)

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# Pydantic Models for LLM Structured Output
# ─────────────────────────────────────────────────────────────────


class RerankOutput(BaseModel):
    """LLM output for repository re-ranking."""

    selected_index: int = Field(
        description="Index (0-based) of the most relevant repository, or -1 if none match"
    )
    reason: str = Field(description="Brief explanation of why this repository was selected")
    # Note: ge/le constraints not supported by Anthropic's Structured Output
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")


# ─────────────────────────────────────────────────────────────────
# Prompt Template
# ─────────────────────────────────────────────────────────────────

RERANK_PROMPT = (
    "You are an expert at matching software entities mentioned in entries "
    "to their GitHub repositories.\n\n"
    "## Task\n"
    "Select the GitHub repository that best matches the software entity "
    '"{query}" mentioned in an entry.\n\n'
    "## Entry Context\n"
    "{context}\n\n"
    "## Repository Candidates\n"
    "{candidates}\n\n"
    "## Instructions\n"
    '1. Consider the entry context to understand what "{query}" refers to\n'
    "2. Match based on:\n"
    "   - Repository name and description alignment with the entity\n"
    "   - Owner/organization credibility (official repos preferred)\n"
    "   - Relevance to the entry topic\n"
    '3. If the owner hint is "{owner_hint}", prefer repositories from that '
    "organization\n"
    "4. Return -1 if none of the candidates are a good match\n\n"
    "Select the most relevant repository."
)


def _format_candidates(candidates: list[dict]) -> str:
    """Format candidates for the prompt."""
    lines = []
    for i, c in enumerate(candidates):
        repo = c.get("repo", {})
        lines.append(
            f"[{i}] {repo.get('full_name', 'unknown')}\n"
            f"    Description: {repo.get('description') or 'No description'}\n"
            f"    Language: {repo.get('language') or 'Unknown'}\n"
            f"    Stars: {repo.get('stars', 0)}\n"
            f"    Topics: {', '.join(repo.get('topics', [])) or 'None'}"
        )
    return "\n\n".join(lines)


def _format_context(input: RerankGitHubInput) -> str:
    """Format entry context for the prompt."""
    parts = []

    if input.entry_title:
        parts.append(f"Title: {input.entry_title}")

    if input.entry_key_points:
        parts.append("Key points:")
        for point in input.entry_key_points[:5]:  # Limit to 5 points
            parts.append(f"  - {point}")

    if input.owner_hint:
        parts.append(f"Owner/Creator hint: {input.owner_hint}")

    return "\n".join(parts) if parts else "No additional context available."


@activity.defn
async def rerank_github_results(
    input: RerankGitHubInput,
) -> RerankGitHubOutput:
    """
    Re-rank GitHub repository candidates using LLM.

    Uses entry context to select the most relevant repository
    from the candidates returned by search_github_candidates.

    Parameters
    ----------
    input : RerankGitHubInput
        Query, candidates, and entry context.

    Returns
    -------
    RerankGitHubOutput
        Selected repository with explanation.
    """
    if not input.candidates:
        logger.debug("No candidates to rerank", query=input.query)
        return RerankGitHubOutput(
            selected=None,
            reason="No candidates provided",
        )

    # Always use LLM to verify relevance, even for single candidates
    # This prevents matching third-party tools instead of official repositories
    logger.info("Re-ranking candidates", count=len(input.candidates), query=input.query)

    config = get_config()

    if not config.openai_api_key:
        logger.error("OPENAI_API_KEY not configured")
        return RerankGitHubOutput(
            selected=None,
            error="OPENAI_API_KEY not configured",
        )

    # Initialize LLM
    # Uses reasoning_llm_model for decision making with Structured Output
    # See: https://docs.langchain.com/oss/python/integrations/chat/anthropic#structured-output
    llm = ChatOpenAI(
        model=config.reasoning_llm_model,
        base_url=config.openai_base_url or None,  # None = OpenAI direct
        api_key=SecretStr(config.openai_api_key),
        temperature=0.0,  # Deterministic for ranking
    )

    # Create structured output chain
    structured_llm = llm.with_structured_output(RerankOutput)

    prompt = ChatPromptTemplate.from_template(RERANK_PROMPT)

    chain = prompt | structured_llm

    try:
        result = await chain.ainvoke(
            {
                "query": input.query,
                "context": _format_context(input),
                "candidates": _format_candidates(input.candidates),
                "owner_hint": input.owner_hint or "none",
            }
        )

        result = RerankOutput.model_validate(result)

        logger.info(
            "LLM selected index",
            selected_index=result.selected_index,
            confidence=round(result.confidence, 2),
            reason=result.reason,
        )

        # Handle no match
        if result.selected_index < 0 or result.selected_index >= len(input.candidates):
            return RerankGitHubOutput(
                selected=None,
                reason=result.reason,
            )

        # Get selected candidate
        selected = input.candidates[result.selected_index]
        repo_dict = selected.get("repo", {})

        return RerankGitHubOutput(
            selected=GitHubRepoInfo(
                owner=repo_dict.get("owner", ""),
                repo=repo_dict.get("repo", ""),
                full_name=repo_dict.get("full_name", ""),
                description=repo_dict.get("description"),
                url=repo_dict.get("url", ""),
                stars=repo_dict.get("stars", 0),
                forks=repo_dict.get("forks", 0),
                language=repo_dict.get("language"),
                topics=repo_dict.get("topics", []),
                license=repo_dict.get("license"),
                updated_at=repo_dict.get("updated_at"),
                open_issues=repo_dict.get("open_issues", 0),
                homepage=repo_dict.get("homepage"),
            ),
            reason=result.reason,
        )

    except Exception as e:
        logger.error(f"Error re-ranking candidates: {e}", query=input.query)
        return RerankGitHubOutput(
            selected=None,
            reason=None,
            error=str(e),
        )
