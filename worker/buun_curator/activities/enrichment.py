"""
Enrichment Activities.

Save and delete enrichment data via REST API.
"""

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    DeleteEnrichmentActivityInput,
    DeleteEnrichmentActivityOutput,
    SaveGitHubEnrichmentInput,
    SaveGitHubEnrichmentOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


@activity.defn
async def save_github_enrichment(
    input: SaveGitHubEnrichmentInput,
) -> SaveGitHubEnrichmentOutput:
    """
    Save GitHub enrichment results to the database.

    Creates separate entry enrichment records for each repository,
    with type='github' and source=repository URL.

    Parameters
    ----------
    input : SaveGitHubEnrichmentInput
        Entry ID and list of enrichment result dicts.

    Returns
    -------
    SaveGitHubEnrichmentOutput
        Success status and count of saved enrichments.
    """
    # Filter only found results with repo data
    found_results = [er for er in input.enrichment_results if er.get("found") and er.get("repo")]

    logger.info("Saving GitHub enrichments", entry_id=input.entry_id, count=len(found_results))

    config = get_config()
    saved_count = 0
    errors: list[str] = []

    try:
        async with APIClient(config.api_url, config.api_token) as client:
            # Delete all existing GitHub enrichments for this entry first
            # (ensures stale enrichments from previous runs are removed)
            delete_result = await client.delete_entry_enrichment(
                entry_id=input.entry_id,
                enrichment_type="github",
                source=None,  # Delete all GitHub enrichments
            )
            if delete_result.get("deleted"):
                deleted_count = delete_result.get("deletedCount", 0)
                logger.debug(
                    "Deleted existing GitHub enrichments",
                    entry_id=input.entry_id,
                    deleted_count=deleted_count,
                )

            if not found_results:
                logger.debug("No valid GitHub repos to save", entry_id=input.entry_id)
                return SaveGitHubEnrichmentOutput(success=True, saved_count=0)
            # Save each repository as a separate enrichment
            for er in found_results:
                repo = er["repo"]
                repo_url = repo.get("url", "")

                enrichment_data = {
                    "entityName": er.get("name"),
                    "owner": repo.get("owner"),
                    "repo": repo.get("repo"),
                    "fullName": repo.get("full_name"),
                    "description": repo.get("description"),
                    "url": repo_url,
                    "stars": repo.get("stars", 0),
                    "forks": repo.get("forks", 0),
                    "language": repo.get("language"),
                    "topics": repo.get("topics", []),
                    "license": repo.get("license"),
                    "homepage": repo.get("homepage"),
                    "readmeFilename": repo.get("readme_filename"),
                    "readmeContent": repo.get("readme_content"),
                }

                result = await client.save_entry_enrichment(
                    entry_id=input.entry_id,
                    enrichment_type="github",
                    data=enrichment_data,
                    source=repo_url,
                )

                if "error" in result:
                    error_msg = f"Failed to save {repo_url}: {result['error']}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                else:
                    saved_count += 1
                    logger.debug("Saved GitHub enrichment", repo_url=repo_url)

            logger.info(
                "Saved GitHub enrichments", entry_id=input.entry_id, saved_count=saved_count
            )

            return SaveGitHubEnrichmentOutput(
                success=len(errors) == 0,
                saved_count=saved_count,
                error="; ".join(errors) if errors else None,
            )

    except Exception as e:
        logger.error(f"Error saving enrichment: {e}", entry_id=input.entry_id)
        return SaveGitHubEnrichmentOutput(
            success=False,
            saved_count=saved_count,
            error=str(e),
        )


@activity.defn
async def delete_enrichment(
    input: DeleteEnrichmentActivityInput,
) -> DeleteEnrichmentActivityOutput:
    """
    Delete an enrichment from the database.

    Parameters
    ----------
    input : DeleteEnrichmentActivityInput
        Entry ID, enrichment type, and source to delete.

    Returns
    -------
    DeleteEnrichmentActivityOutput
        Whether the enrichment was deleted.
    """
    logger.info(
        "Deleting enrichment",
        entry_id=input.entry_id,
        enrichment_type=input.enrichment_type,
        source=input.source,
    )

    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as client:
            result = await client.delete_entry_enrichment(
                entry_id=input.entry_id,
                enrichment_type=input.enrichment_type,
                source=input.source,
            )

            if "error" in result:
                logger.warning(f"Enrichment not found or already deleted: {result['error']}")
                return DeleteEnrichmentActivityOutput(deleted=False, error=result["error"])

            logger.info(
                "Deleted enrichment",
                enrichment_type=input.enrichment_type,
                source=input.source,
            )
            return DeleteEnrichmentActivityOutput(deleted=True)

    except Exception as e:
        logger.error(f"Error deleting enrichment: {e}")
        return DeleteEnrichmentActivityOutput(deleted=False, error=str(e))
