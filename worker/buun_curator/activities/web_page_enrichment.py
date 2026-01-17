"""
Web page enrichment save Activity.

Save web page enrichment results to the database via REST API.
"""

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    SaveWebPageEnrichmentInput,
    SaveWebPageEnrichmentOutput,
)
from buun_curator.services.api import APIClient

logger = get_logger(__name__)


@activity.defn
async def save_web_page_enrichment(
    input: SaveWebPageEnrichmentInput,
) -> SaveWebPageEnrichmentOutput:
    """
    Save web page enrichment results to the database.

    Creates an entry enrichment record with type='web_page' containing
    all unique web page URLs found in the entry.

    Parameters
    ----------
    input : SaveWebPageEnrichmentInput
        Entry ID and list of web page info.

    Returns
    -------
    SaveWebPageEnrichmentOutput
        Success status and count of saved web pages.
    """
    if not input.web_pages:
        logger.debug("No web pages to save", entry_id=input.entry_id)
        return SaveWebPageEnrichmentOutput(success=True, saved_count=0)

    logger.info(
        "Saving web pages", entry_id=input.entry_id, pages=len(input.web_pages)
    )

    config = get_config()

    try:
        async with APIClient(config.api_url, config.api_token) as client:
            # Build enrichment data
            enrichment_data = {
                "webPages": [
                    {
                        "url": wp.url,
                        "title": wp.title,
                    }
                    for wp in input.web_pages
                ],
            }

            result = await client.save_entry_enrichment(
                entry_id=input.entry_id,
                enrichment_type="web_page",
                data=enrichment_data,
                source="extracted_links",
            )

            if "error" in result:
                logger.error(
                    f"Failed to save web page enrichment: {result['error']}",
                    entry_id=input.entry_id,
                )
                return SaveWebPageEnrichmentOutput(
                    success=False,
                    error=result["error"],
                )

            logger.info(
                "Saved web page enrichment",
                entry_id=input.entry_id,
                pages=len(input.web_pages),
            )

            return SaveWebPageEnrichmentOutput(
                success=True,
                saved_count=len(input.web_pages),
            )

    except Exception as e:
        logger.error(f"Error saving web page enrichment: {e}", entry_id=input.entry_id)
        return SaveWebPageEnrichmentOutput(
            success=False,
            error=str(e),
        )
