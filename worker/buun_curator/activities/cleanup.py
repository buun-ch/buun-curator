"""
Cleanup Activities.

Delete old entries via REST API.
"""

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    CleanupOldEntriesInput,
    CleanupOldEntriesOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


@activity.defn
async def cleanup_old_entries(
    input: CleanupOldEntriesInput,
) -> CleanupOldEntriesOutput:
    """
    Delete old entries that meet cleanup criteria.

    Criteria:
    - isRead = true
    - isStarred = false
    - keep = false
    - publishedAt is older than the specified days

    Parameters
    ----------
    input : CleanupOldEntriesInput
        Cleanup parameters including older_than_days and dry_run.

    Returns
    -------
    CleanupOldEntriesOutput
        Result with deleted_count and cutoff_date.
    """
    logger.info(
        "Cleaning up old entries",
        older_than_days=input.older_than_days,
        dry_run=input.dry_run,
    )

    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as client:
            result = await client._request(
                "POST",
                "/api/entries/cleanup",
                json={
                    "olderThanDays": input.older_than_days,
                    "dryRun": input.dry_run,
                },
            )

            if isinstance(result, dict):
                if "error" in result:
                    logger.error(f"Cleanup failed: {result['error']}")
                    return CleanupOldEntriesOutput(
                        error=result["error"],
                        older_than_days=input.older_than_days,
                        dry_run=input.dry_run,
                    )

                deleted_count = result.get("deletedCount", result.get("count", 0))
                deleted_ids = result.get("deletedIds", [])
                cutoff_date = result.get("cutoffDate", "")

                action = "Would delete" if input.dry_run else "Deleted"
                logger.info(
                    "Cleanup completed",
                    action=action,
                    deleted_count=deleted_count,
                    cutoff_date=cutoff_date,
                )

                return CleanupOldEntriesOutput(
                    deleted_count=deleted_count,
                    deleted_ids=deleted_ids,
                    dry_run=input.dry_run,
                    older_than_days=input.older_than_days,
                    cutoff_date=cutoff_date,
                )

            return CleanupOldEntriesOutput(
                error="Unexpected response format",
                older_than_days=input.older_than_days,
                dry_run=input.dry_run,
            )

    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return CleanupOldEntriesOutput(
            error=str(e),
            older_than_days=input.older_than_days,
            dry_run=input.dry_run,
        )
