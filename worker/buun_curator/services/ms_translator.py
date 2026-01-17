"""
Microsoft Translator Service for Buun Curator.

API-based entry translation using Azure Cognitive Services Translator.

Uses Markdown → HTML → Microsoft Translator (textType=html) → Markdown conversion
to preserve formatting during translation.
"""

import re

import httpx
import markdown
from crawl4ai.html2text import HTML2Text

from buun_curator.logging import get_logger
from buun_curator.models.entry import EntryToTranslate, TranslatedEntry

logger = get_logger(__name__)

# Microsoft Translator API endpoint
MS_TRANSLATOR_API_URL = "https://api.cognitive.microsofttranslator.com/translate"
MS_TRANSLATOR_API_VERSION = "3.0"

# Microsoft Translator language codes mapping
# Microsoft uses different codes for some languages
LANGUAGE_CODE_MAP = {
    "en": "en",
    "ja": "ja",
    "zh": "zh-Hans",  # Simplified Chinese
    "zh-tw": "zh-Hant",  # Traditional Chinese
    "ko": "ko",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "pt": "pt-br",  # Brazilian Portuguese
}


def _markdown_to_html(md_text: str) -> str:
    """
    Convert Markdown to HTML.

    Parameters
    ----------
    md_text : str
        Markdown text.

    Returns
    -------
    str
        HTML content.
    """
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "nl2br"],
    )


def _protect_code_blocks(html: str) -> str:
    """
    Add translate="no" attribute to code blocks to prevent translation.

    Microsoft Translator respects the translate="no" attribute on HTML elements,
    preserving their content as-is during translation.

    Parameters
    ----------
    html : str
        HTML content.

    Returns
    -------
    str
        HTML with protected code blocks.
    """
    # Add translate="no" to <pre> tags (includes fenced code blocks)
    html = re.sub(r"<pre>", '<pre translate="no">', html)
    # Add translate="no" to <code> tags (inline code)
    html = re.sub(r"<code>", '<code translate="no">', html)
    return html


def _html_to_markdown(html: str) -> str:
    """
    Convert HTML back to Markdown.

    Parameters
    ----------
    html : str
        HTML content.

    Returns
    -------
    str
        Markdown text.
    """
    h2t = HTML2Text()
    h2t.body_width = 0  # No line wrapping
    h2t.ignore_images = False
    h2t.ignore_links = False
    h2t.protect_links = True
    h2t.unicode_snob = True  # Use unicode instead of ASCII
    return h2t.handle(html).strip()


class MSTranslator:
    """Service for translating entries using Microsoft Translator API."""

    def __init__(
        self,
        subscription_key: str,
        region: str,
        target_language: str,
    ):
        """
        Initialize the Microsoft Translator.

        Parameters
        ----------
        subscription_key : str
            Azure Cognitive Services subscription key.
        region : str
            Azure region (e.g., "japaneast", "eastus").
        target_language : str
            Target language code for translations (e.g., "ja", "en").
        """
        self.subscription_key = subscription_key
        self.region = region
        self.target_language = target_language

    def _get_ms_lang_code(self, lang: str) -> str:
        """
        Convert internal language code to Microsoft Translator format.

        Parameters
        ----------
        lang : str
            Internal language code.

        Returns
        -------
        str
            Microsoft Translator language code.
        """
        return LANGUAGE_CODE_MAP.get(lang, lang)

    async def translate_single(self, entry: EntryToTranslate) -> TranslatedEntry:
        """
        Translate a single entry using Microsoft Translator API.

        If content is already HTML (is_html=True), sends directly to the API.
        If content is Markdown, converts to HTML first, then translates.
        Always returns Markdown.

        Parameters
        ----------
        entry : EntryToTranslate
            Entry to translate.

        Returns
        -------
        TranslatedEntry
            Translated entry in Markdown format.
        """
        if not entry.full_content.strip():
            return TranslatedEntry(
                entry_id=entry.entry_id,
                translated_content="",
            )

        target_lang = self._get_ms_lang_code(self.target_language)

        # Determine HTML content based on source format
        if entry.is_html:
            # Already HTML (feedContent), use directly
            html_content = entry.full_content
        else:
            # Markdown (fullContent), convert to HTML first
            html_content = _markdown_to_html(entry.full_content)

        # Protect code blocks from translation
        html_content = _protect_code_blocks(html_content)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    MS_TRANSLATOR_API_URL,
                    params={
                        "api-version": MS_TRANSLATOR_API_VERSION,
                        "to": target_lang,
                        "textType": "html",  # Preserve HTML structure
                    },
                    headers={
                        "Ocp-Apim-Subscription-Key": self.subscription_key,
                        "Ocp-Apim-Subscription-Region": self.region,
                        "Content-Type": "application/json",
                    },
                    json=[{"Text": html_content}],
                )
                response.raise_for_status()

                data = response.json()

                if data and len(data) > 0:
                    translations = data[0].get("translations", [])
                    if translations:
                        translated_html = translations[0].get("text", "")
                        # Convert HTML back to Markdown
                        translated_md = _html_to_markdown(translated_html)
                        return TranslatedEntry(
                            entry_id=entry.entry_id,
                            translated_content=translated_md,
                        )

                logger.warning("No translation returned", entry_id=entry.entry_id)
                return TranslatedEntry(
                    entry_id=entry.entry_id,
                    translated_content="",
                )

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Microsoft Translator API error for {entry.entry_id}: "
                    f"{e.response.status_code} - {e.response.text}",
                    error_type=type(e).__name__,
                )
                return TranslatedEntry(
                    entry_id=entry.entry_id,
                    translated_content="",
                )
            except Exception as e:
                logger.error(
                    f"Error translating entry: {e}",
                    entry_id=entry.entry_id,
                    error_type=type(e).__name__,
                )
                return TranslatedEntry(
                    entry_id=entry.entry_id,
                    translated_content="",
                )

    async def translate(self, entries: list[EntryToTranslate]) -> list[TranslatedEntry]:
        """
        Translate entries sequentially.

        Parameters
        ----------
        entries : list[EntryToTranslate]
            List of entries to translate.

        Returns
        -------
        list[TranslatedEntry]
            List of translated entries.
        """
        if not entries:
            logger.info("No entries to translate")
            return []

        # Filter out entries without content
        entries_with_content = [e for e in entries if e.full_content.strip()]

        if not entries_with_content:
            logger.info("No entries with content to translate")
            return []

        total = len(entries_with_content)
        logger.info("Translating entries with Microsoft Translator", total=total)

        results: list[TranslatedEntry] = []

        for i, entry in enumerate(entries_with_content):
            logger.debug("Translating entry", index=i + 1, total=total, entry_id=entry.entry_id)
            result = await self.translate_single(entry)
            results.append(result)

        success_count = sum(1 for r in results if r.translated_content)
        logger.info(
            "Microsoft Translator translation completed",
            success_count=success_count,
            total=total,
        )

        return results
