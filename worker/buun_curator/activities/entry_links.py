"""
Entry links save Activity.

Save extracted links to the database via REST API.
"""

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    SaveEntryLinksInput,
    SaveEntryLinksOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


@activity.defn
async def save_entry_links(
    input: SaveEntryLinksInput,
) -> SaveEntryLinksOutput:
    """
    Save extracted links to the database.

    Create entry_links records for all unique links found in the entry.

    Parameters
    ----------
    input : SaveEntryLinksInput
        Entry ID and list of link info.

    Returns
    -------
    SaveEntryLinksOutput
        Success status and count of saved links.
    """
    if not input.links:
        logger.debug("No links to save", entry_id=input.entry_id)
        return SaveEntryLinksOutput(success=True, saved_count=0)

    logger.info("Saving links", entry_id=input.entry_id, links=len(input.links))

    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as client:
            links_data = [{"url": link.url, "title": link.title} for link in input.links]

            result = await client.save_entry_links(
                entry_id=input.entry_id,
                links=links_data,
            )

            if "error" in result:
                logger.error(f"Failed to save links: {result['error']}", entry_id=input.entry_id)
                return SaveEntryLinksOutput(
                    success=False,
                    error=result["error"],
                )

            saved_count = result.get("savedCount", len(input.links))
            logger.info("Saved links", entry_id=input.entry_id, saved_count=saved_count)

            return SaveEntryLinksOutput(
                success=True,
                saved_count=saved_count,
            )

    except Exception as e:
        logger.error(f"Error saving links: {e}", entry_id=input.entry_id)
        return SaveEntryLinksOutput(
            success=False,
            error=str(e),
        )
