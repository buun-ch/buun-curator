"""
GitHub enrichment Activity.

Search GitHub repositories for software entities and retrieve metadata.
Uses githubkit for async GitHub API access.
"""

import base64
import re

from githubkit import GitHub
from githubkit.exception import RequestFailed
from githubkit.versions.latest.models import FullRepository, RepoSearchResultItem
from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    FetchGitHubReadmeInput,
    FetchGitHubReadmeOutput,
    GitHubCandidate,
    GitHubRepoInfo,
    SearchGitHubCandidatesInput,
    SearchGitHubCandidatesOutput,
    SearchGitHubInput,
    SearchGitHubOutput,
)

logger = get_logger(__name__)

# Well-known software that doesn't need GitHub enrichment
# (too generic or ubiquitous)
SKIP_SOFTWARE = {
    "python",
    "javascript",
    "typescript",
    "java",
    "rust",
    "go",
    "ruby",
    "php",
    "c",
    "c++",
    "c#",
    "swift",
    "kotlin",
    "scala",
    "perl",
    "r",
    "matlab",
    "sql",
    "html",
    "css",
    "shell",
    "bash",
    "powershell",
    "vs code",
    "visual studio code",
    "visual studio",
    "vscode",
    "pycharm",
    "intellij",
    "eclipse",
    "xcode",
    "vim",
    "neovim",
    "emacs",
    "sublime text",
    "atom",
    "notepad++",
    "git",
    "github",
    "gitlab",
    "bitbucket",
    "docker",
    "kubernetes",
    "linux",
    "windows",
    "macos",
    "android",
    "ios",
    "chrome",
    "firefox",
    "safari",
    "edge",
    "node.js",
    "nodejs",
    "npm",
    "yarn",
    "pip",
    "conda",
    "homebrew",
    "apt",
    "wasm",
    "webassembly",
}

# Company name to GitHub org mapping
COMPANY_TO_GITHUB_ORG = {
    "meta": "facebook",
    "facebook": "facebook",
    "google": "google",
    "microsoft": "microsoft",
    "amazon": "amazon",
    "aws": "aws",
    "apple": "apple",
    "netflix": "netflix",
    "uber": "uber",
    "airbnb": "airbnb",
    "twitter": "twitter",
    "x": "twitter",
    "astral": "astral-sh",
    "vercel": "vercel",
    "cloudflare": "cloudflare",
    "hashicorp": "hashicorp",
    "databricks": "databricks",
    "snowflake": "snowflake",
    "openai": "openai",
    "anthropic": "anthropic",
    "hugging face": "huggingface",
    "huggingface": "huggingface",
}


def _should_skip_entity(name: str) -> bool:
    """Check if entity should be skipped for GitHub enrichment."""
    return name.lower() in SKIP_SOFTWARE


def _get_github_org(company_name: str | None) -> str | None:
    """Convert company name to GitHub organization name."""
    if not company_name:
        return None
    return COMPANY_TO_GITHUB_ORG.get(company_name.lower())


def _repo_to_info(repo: FullRepository | RepoSearchResultItem) -> GitHubRepoInfo:
    """Convert githubkit repository model to GitHubRepoInfo."""
    return GitHubRepoInfo(
        owner=repo.owner.login if repo.owner else "",
        repo=repo.name,
        full_name=repo.full_name,
        description=repo.description,
        url=repo.html_url,
        stars=repo.stargazers_count or 0,
        forks=repo.forks_count or 0,
        language=repo.language,
        topics=list(repo.topics) if repo.topics else [],
        license=repo.license_.spdx_id if repo.license_ else None,
        updated_at=repo.updated_at.isoformat() if repo.updated_at else None,
        open_issues=repo.open_issues_count or 0,
        homepage=repo.homepage or None,
    )


def _calculate_relevance_score(
    query: str,
    repo: RepoSearchResultItem,
    owner_hint: str | None = None,
) -> float:
    """
    Calculate relevance score for a search result.

    Parameters
    ----------
    query : str
        The search query (entity name).
    repo : RepoSearchResultItem
        GitHub search result item.
    owner_hint : str | None
        Optional owner hint from context.

    Returns
    -------
    float
        Relevance score (higher is better). Returns 0 if not relevant.
    """
    score = 0.0
    query_lower = query.lower()
    repo_name = repo.name.lower()
    full_name = repo.full_name.lower()
    description = (repo.description or "").lower()

    # Exact match in repo name (highest priority)
    if repo_name == query_lower:
        score += 100.0

    # Repo name starts with query
    elif repo_name.startswith(query_lower):
        score += 50.0

    # Query is a word boundary match in repo name
    # e.g., "ty" matches "ty" or "ty-something" but not "typescript"
    elif re.search(rf"\b{re.escape(query_lower)}\b", repo_name):
        score += 40.0

    # Query in full_name (owner/repo) with word boundary
    elif re.search(rf"\b{re.escape(query_lower)}\b", full_name):
        score += 30.0

    # Query appears in description with word boundary
    if description and re.search(rf"\b{re.escape(query_lower)}\b", description):
        score += 10.0

    # Bonus: owner matches hint
    if owner_hint:
        github_org = _get_github_org(owner_hint)
        owner_login = repo.owner.login.lower() if repo.owner else ""
        if github_org and owner_login == github_org.lower():
            score += 20.0

    # Penalty: query is too small a fraction of repo name
    # Avoid matching "ty" to "typescript" (2/10 = 0.2)
    # Only apply penalty if we don't have a word boundary match
    if (
        repo_name
        and len(query_lower) < len(repo_name) * 0.5
        and not re.search(rf"\b{re.escape(query_lower)}\b", repo_name)
    ):
        score *= 0.1

    return score


async def _fetch_repo_info(
    gh: GitHub,
    owner: str,
    repo: str,
) -> GitHubRepoInfo | None:
    """Fetch repository information from GitHub API."""
    try:
        response = await gh.rest.repos.async_get(owner=owner, repo=repo)
        return _repo_to_info(response.parsed_data)

    except RequestFailed as e:
        if e.response.status_code == 404:
            logger.debug("Repository not found", owner=owner, repo=repo)
        elif e.response.status_code == 403:
            logger.warning("GitHub API rate limit exceeded")
        else:
            logger.warning(f"GitHub API error: {e}", owner=owner, repo=repo)
        return None

    except Exception as e:
        logger.error(f"Error fetching repository: {e}", owner=owner, repo=repo)
        return None


async def _search_repositories(
    gh: GitHub,
    query: str,
    owner_hint: str | None = None,
) -> GitHubRepoInfo | None:
    """
    Search GitHub repositories.

    If owner_hint is provided, tries direct repo lookup first,
    then falls back to search.
    """
    # Try direct lookup if we have an owner hint
    if owner_hint:
        github_org = _get_github_org(owner_hint)
        if github_org:
            # Try exact match: owner/query
            repo_info = await _fetch_repo_info(gh, github_org, query.lower())
            if repo_info:
                logger.info("Found repo via direct lookup", full_name=repo_info.full_name)
                return repo_info

            # Try with hyphenated name (e.g., "Pyrefly" -> "pyrefly")
            repo_info = await _fetch_repo_info(
                gh,
                github_org,
                query.lower().replace(" ", "-"),
            )
            if repo_info:
                logger.info("Found repo via direct lookup", full_name=repo_info.full_name)
                return repo_info

    # Fall back to search API
    search_query = query
    if owner_hint:
        github_org = _get_github_org(owner_hint)
        if github_org:
            search_query = f"{query} user:{github_org}"

    try:
        response = await gh.rest.search.async_repos(
            q=search_query,
            sort="stars",
            order="desc",
            per_page=10,
        )
        items = response.parsed_data.items

        if not items:
            logger.debug("No repositories found for query", query=search_query)
            return None

        # Score all results and pick the best one
        scored_items = [
            (item, _calculate_relevance_score(query, item, owner_hint)) for item in items
        ]

        # Sort by score (descending)
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Log scores for debugging
        for item, score in scored_items[:5]:
            logger.debug("Candidate score", full_name=item.full_name, score=round(score, 1))

        # Get the best match
        best_item, best_score = scored_items[0]

        # Require minimum relevance score
        if best_score < 10.0:
            logger.debug(
                "Best match has low score, rejecting",
                full_name=best_item.full_name,
                score=round(best_score, 1),
            )
            return None

        logger.debug(
            "Selected best match", full_name=best_item.full_name, score=round(best_score, 1)
        )

        return _repo_to_info(best_item)

    except RequestFailed as e:
        if e.response.status_code == 403:
            logger.warning("GitHub API rate limit exceeded for search")
        else:
            logger.warning(f"GitHub search API error: {e}")
        return None

    except Exception as e:
        logger.error(f"Error searching for repository: {e}", query=query)
        return None


async def _search_repository_candidates(
    gh: GitHub,
    query: str,
    owner_hint: str | None = None,
    max_candidates: int = 5,
) -> list[GitHubCandidate]:
    """
    Search GitHub repositories and return multiple candidates with scores.

    Parameters
    ----------
    gh : GitHub
        GitHub client.
    query : str
        Search query (entity name).
    owner_hint : str | None
        Optional owner hint from context.
    max_candidates : int
        Maximum number of candidates to return.

    Returns
    -------
    list[GitHubCandidate]
        List of repository candidates with scores, sorted by score descending.
    """
    candidates: list[GitHubCandidate] = []

    # Try direct lookup if we have an owner hint
    if owner_hint:
        github_org = _get_github_org(owner_hint)
        if github_org:
            # Try exact match: owner/query
            repo_info = await _fetch_repo_info(gh, github_org, query.lower())
            if repo_info:
                logger.info("Found repo via direct lookup", full_name=repo_info.full_name)
                # Direct lookup gets highest score
                candidates.append(GitHubCandidate(repo=repo_info, score=150.0))

            # Try with hyphenated name
            if not candidates:
                repo_info = await _fetch_repo_info(
                    gh,
                    github_org,
                    query.lower().replace(" ", "-"),
                )
                if repo_info:
                    logger.info("Found repo via direct lookup", full_name=repo_info.full_name)
                    candidates.append(GitHubCandidate(repo=repo_info, score=150.0))

    # Fall back to search API
    search_query = query
    if owner_hint:
        github_org = _get_github_org(owner_hint)
        if github_org:
            search_query = f"{query} user:{github_org}"

    try:
        response = await gh.rest.search.async_repos(
            q=search_query,
            sort="stars",
            order="desc",
            per_page=10,
        )
        items = response.parsed_data.items

        if not items:
            logger.debug("No repositories found for query", query=search_query)
            return candidates

        # Score all results
        for item in items:
            score = _calculate_relevance_score(query, item, owner_hint)

            # Skip very low scores
            if score < 1.0:
                continue

            repo_info = _repo_to_info(item)

            # Avoid duplicates (from direct lookup)
            if not any(c.repo.full_name == repo_info.full_name for c in candidates):
                candidates.append(GitHubCandidate(repo=repo_info, score=score))

        # Sort by score descending
        candidates.sort(key=lambda c: c.score, reverse=True)

        # Log candidates for debugging
        for c in candidates[:5]:
            logger.debug("Candidate", full_name=c.repo.full_name, score=round(c.score, 1))

        # Return top candidates
        return candidates[:max_candidates]

    except RequestFailed as e:
        if e.response.status_code == 403:
            logger.warning("GitHub API rate limit exceeded for search")
        else:
            logger.warning(f"GitHub search API error: {e}")
        return candidates

    except Exception as e:
        logger.error(f"Error searching for repository: {e}", query=query)
        return candidates


@activity.defn
async def search_github_repository(
    input: SearchGitHubInput,
) -> SearchGitHubOutput:
    """
    Search GitHub for a repository matching the query.

    Supports direct repo lookup when owner_hint is provided,
    with fallback to search API.

    Parameters
    ----------
    input : SearchGitHubInput
        Query string and optional owner hint.

    Returns
    -------
    SearchGitHubOutput
        Search result with repository info if found.
    """
    query = input.query.strip()

    # Skip well-known software
    if _should_skip_entity(query):
        logger.debug("Skipping well-known software", query=query)
        return SearchGitHubOutput(found=False)

    logger.info("Searching GitHub", query=query, owner_hint=input.owner_hint)

    config = get_config()
    token = config.github_token if config.github_token else None

    async with GitHub(token) as gh:
        repo_info = await _search_repositories(gh, query, input.owner_hint)

        if repo_info:
            logger.info(
                "Found repository",
                full_name=repo_info.full_name,
                stars=repo_info.stars,
                language=repo_info.language,
            )
            return SearchGitHubOutput(found=True, repo=repo_info)

        logger.debug("No repository found", query=query)
        return SearchGitHubOutput(found=False)


@activity.defn
async def search_github_candidates(
    input: SearchGitHubCandidatesInput,
) -> SearchGitHubCandidatesOutput:
    """
    Search GitHub for repository candidates matching the query.

    Returns multiple candidates with relevance scores for LLM re-ranking.

    Parameters
    ----------
    input : SearchGitHubCandidatesInput
        Query string, optional owner hint, and max candidates.

    Returns
    -------
    SearchGitHubCandidatesOutput
        List of repository candidates with scores.
    """
    query = input.query.strip()

    # Skip well-known software
    if _should_skip_entity(query):
        logger.debug("Skipping well-known software", query=query)
        return SearchGitHubCandidatesOutput(candidates=[])

    logger.info("Searching GitHub candidates", query=query, owner_hint=input.owner_hint)

    config = get_config()
    token = config.github_token if config.github_token else None

    async with GitHub(token) as gh:
        candidates = await _search_repository_candidates(
            gh,
            query,
            input.owner_hint,
            input.max_candidates,
        )

        logger.info("Found candidates", count=len(candidates), query=query)
        for c in candidates:
            logger.info("Candidate result", full_name=c.repo.full_name, score=round(c.score, 1))

        return SearchGitHubCandidatesOutput(candidates=candidates)


@activity.defn
async def fetch_github_readme(
    input: FetchGitHubReadmeInput,
) -> FetchGitHubReadmeOutput:
    """
    Fetch README content from a GitHub repository.

    Parameters
    ----------
    input : FetchGitHubReadmeInput
        Repository owner and name.

    Returns
    -------
    FetchGitHubReadmeOutput
        README filename and decoded content if found.
    """
    logger.info("Fetching README", owner=input.owner, repo=input.repo)

    config = get_config()
    token = config.github_token if config.github_token else None

    try:
        async with GitHub(token) as gh:
            response = await gh.rest.repos.async_get_readme(
                owner=input.owner,
                repo=input.repo,
            )
            readme = response.parsed_data

            # Decode Base64 content
            if readme.content and readme.encoding == "base64":
                # Remove newlines that GitHub adds to the base64 content
                content_b64 = readme.content.replace("\n", "")
                content = base64.b64decode(content_b64).decode("utf-8")

                logger.info(
                    "Fetched README",
                    filename=readme.name,
                    chars=len(content),
                    owner=input.owner,
                    repo=input.repo,
                )

                return FetchGitHubReadmeOutput(
                    found=True,
                    filename=readme.name,
                    content=content,
                )

            logger.warning(
                "Unexpected README encoding",
                encoding=readme.encoding,
                owner=input.owner,
                repo=input.repo,
            )
            return FetchGitHubReadmeOutput(
                found=False,
                error=f"Unexpected encoding: {readme.encoding}",
            )

    except RequestFailed as e:
        if e.response.status_code == 404:
            logger.debug("No README found", owner=input.owner, repo=input.repo)
            return FetchGitHubReadmeOutput(found=False)
        elif e.response.status_code == 403:
            logger.warning("GitHub API rate limit exceeded")
            return FetchGitHubReadmeOutput(
                found=False,
                error="Rate limit exceeded",
            )
        else:
            logger.warning(f"GitHub API error: {e}", owner=input.owner, repo=input.repo)
            return FetchGitHubReadmeOutput(
                found=False,
                error=str(e),
            )

    except Exception as e:
        logger.error(f"Error fetching README: {e}", owner=input.owner, repo=input.repo)
        return FetchGitHubReadmeOutput(
            found=False,
            error=str(e),
        )
