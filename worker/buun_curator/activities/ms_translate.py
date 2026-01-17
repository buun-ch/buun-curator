"""
Microsoft Translator Activities for Temporal.

Activities for entry translation using Azure Cognitive Services Translator.
"""

from temporalio import activity

from buun_curator.config import get_config
from buun_curator.logging import get_logger
from buun_curator.models import (
    TranslateEntriesInput,
    TranslateEntriesOutput,
)
from buun_curator.models.entry import EntryToTranslate
from buun_curator.services.ms_translator import MSTranslator

logger = get_logger(__name__)


@activity.defn
async def ms_translate_entries(
    input: TranslateEntriesInput,
) -> TranslateEntriesOutput:
    """
    Translate a list of entries using Microsoft Translator API.

    Parameters
    ----------
    input : TranslateEntriesInput
        Input containing entries list, batch_size, and target_language.

    Returns
    -------
    TranslateEntriesOutput
        Output containing list of translation dicts.
    """
    if not input.entries:
        logger.info("No entries to translate")
        return TranslateEntriesOutput()

    if not input.target_language:
        logger.error("No target language specified for translation")
        return TranslateEntriesOutput()

    config = get_config()

    if not config.ms_translator_subscription_key:
        logger.error("MS_TRANSLATOR_SUBSCRIPTION_KEY not configured")
        return TranslateEntriesOutput()

    if not config.ms_translator_region:
        logger.error("MS_TRANSLATOR_REGION not configured")
        return TranslateEntriesOutput()

    logger.info(
        "MS translate start",
        entries=len(input.entries),
        target_language=input.target_language,
    )

    translator = MSTranslator(
        subscription_key=config.ms_translator_subscription_key,
        region=config.ms_translator_region,
        target_language=input.target_language,
    )

    # Convert dicts to EntryToTranslate objects
    entries_to_translate = [
        EntryToTranslate(
            entry_id=e["entry_id"],
            title=e.get("title", ""),
            url=e.get("url", ""),
            full_content=e.get("full_content", ""),
            is_html=e.get("is_html", False),
        )
        for e in input.entries
        if e.get("full_content", "").strip()
    ]

    if not entries_to_translate:
        logger.info("No entries with content to translate")
        return TranslateEntriesOutput()

    # Translate with heartbeat for long-running operations
    total = len(entries_to_translate)
    activity.heartbeat(f"Starting Microsoft Translator translation: {total} entries")

    results: list[dict] = []

    for i, entry in enumerate(entries_to_translate):
        activity.heartbeat(f"Translating entry {i + 1}/{total}")

        result = await translator.translate_single(entry)
        results.append(
            {
                "entry_id": result.entry_id,
                "translated_content": result.translated_content,
            }
        )

    success_count = sum(1 for r in results if r.get("translated_content"))
    activity.heartbeat(f"Completed: {success_count}/{total} successful")
    logger.info(
        "Microsoft Translator translate completed",
        success_count=success_count,
        total=total,
    )

    return TranslateEntriesOutput(translations=results)
