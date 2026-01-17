"""
DeepL Translator Service for Buun Curator.

API-based entry translation using DeepL.

Uses Markdown → HTML → DeepL (tag_handling=html) → Markdown conversion
to preserve formatting during translation.
"""

import httpx
import markdown
from crawl4ai.html2text import HTML2Text

from buun_curator.logging import get_logger
from buun_curator.models.entry import EntryToTranslate, TranslatedEntry

logger = get_logger(__name__)

# DeepL API endpoints
DEEPL_API_URL = "https://api-free.deepl.com/v2/translate"
DEEPL_PRO_API_URL = "https://api.deepl.com/v2/translate"

# DeepL language codes mapping
# DeepL uses different codes than our internal codes in some cases
LANGUAGE_CODE_MAP = {
    "en": "EN",
    "ja": "JA",
    "zh": "ZH",
    "ko": "KO",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
    "pt": "PT-BR",  # Default to Brazilian Portuguese
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


class DeepLTranslator:
    """Service for translating entries using DeepL API."""

    def __init__(
        self,
        api_key: str,
        target_language: str,
        use_pro: bool = False,
    ):
        """
        Initialize the DeepL translator.

        Parameters
        ----------
        api_key : str
            DeepL API key.
        target_language : str
            Target language code for translations (e.g., "ja", "en").
        use_pro : bool, optional
            Use DeepL Pro API endpoint (default: False).
        """
        self.api_key = api_key
        self.target_language = target_language
        self.api_url = DEEPL_PRO_API_URL if use_pro else DEEPL_API_URL

    def _get_deepl_lang_code(self, lang: str) -> str:
        """
        Convert internal language code to DeepL format.

        Parameters
        ----------
        lang : str
            Internal language code.

        Returns
        -------
        str
            DeepL language code.
        """
        return LANGUAGE_CODE_MAP.get(lang, lang.upper())

    async def translate_single(self, entry: EntryToTranslate) -> TranslatedEntry:
        """
        Translate a single entry using DeepL API.

        If content is already HTML (is_html=True), sends directly to DeepL.
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

        target_lang = self._get_deepl_lang_code(self.target_language)

        # Determine HTML content based on source format
        if entry.is_html:
            # Already HTML (feedContent), use directly
            html_content = entry.full_content
        else:
            # Markdown (fullContent), convert to HTML first
            html_content = _markdown_to_html(entry.full_content)

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"DeepL-Auth-Key {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": [html_content],
                        "target_lang": target_lang,
                        "tag_handling": "html",  # Preserve HTML structure
                        "split_sentences": "nonewlines",  # Don't split on newlines
                    },
                )
                response.raise_for_status()

                data = response.json()
                translations = data.get("translations", [])

                if translations:
                    translated_html = translations[0].get("text", "")
                    # Convert HTML back to Markdown
                    translated_md = _html_to_markdown(translated_html)
                    return TranslatedEntry(
                        entry_id=entry.entry_id,
                        translated_content=translated_md,
                    )
                else:
                    logger.warning("No translation returned", entry_id=entry.entry_id)
                    return TranslatedEntry(
                        entry_id=entry.entry_id,
                        translated_content="",
                    )

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"DeepL API error for {entry.entry_id}: "
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
        logger.info("Translating entries with DeepL", total=total)

        results: list[TranslatedEntry] = []

        for i, entry in enumerate(entries_with_content):
            logger.debug("Translating entry", index=i + 1, total=total, entry_id=entry.entry_id)
            result = await self.translate_single(entry)
            results.append(result)

        success_count = sum(1 for r in results if r.translated_content)
        logger.info(
            "DeepL translation completed",
            success_count=success_count,
            total=total,
        )

        return results
