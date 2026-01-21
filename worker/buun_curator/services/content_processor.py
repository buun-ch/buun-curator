"""
Content Processor Service for Buun Curator.

LangChain-based entry content processing (filtering + summarization).
"""

from collections.abc import Callable

from langchain_openai import ChatOpenAI
from langfuse import get_client
from pydantic import SecretStr

from buun_curator.chains.content_processing import (
    create_batch_content_processing_chain,
    create_content_processing_chain,
)
from buun_curator.logging import get_logger
from buun_curator.models.entry import (
    BatchContentProcessingOutput,
    ContentProcessingLLMOutput,
    EntryToProcess,
    ProcessedEntry,
)
from buun_curator.utils.trace import generate_entry_trace_id

logger = get_logger(__name__)

LANGUAGE_NAMES = {
    "en": "English",
    "ja": "Japanese",
    "zh": "Chinese",
    "ko": "Korean",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
}


def _add_line_numbers(content: str) -> str:
    """
    Add line numbers to content for LLM processing.

    Parameters
    ----------
    content : str
        Original content.

    Returns
    -------
    str
        Content with line numbers prefixed to each line.
    """
    lines = content.split("\n")
    numbered_lines = [f"{i + 1}: {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def _extract_main_content(
    content: str,
    start_line: int,
    end_line: int,
) -> str:
    """
    Extract main content from start_line to end_line (1-indexed, inclusive).

    Parameters
    ----------
    content : str
        Original content.
    start_line : int
        First line of main content (1-indexed).
    end_line : int
        Last line of main content (1-indexed).

    Returns
    -------
    str
        Extracted content, or original if extraction is too aggressive.
    """
    lines = content.split("\n")
    total_lines = len(lines)

    if total_lines == 0:
        return content

    # Convert 1-indexed to 0-indexed for Python slicing
    # start_line=1 means index 0, end_line=10 means we want lines[0:10]
    start_idx = max(0, start_line - 1)
    end_idx = min(total_lines, end_line)  # end_line is inclusive, so slice to end_line

    # Validate range
    if start_idx >= end_idx:
        logger.warning(
            f"Invalid line range "
            f"(start_line={start_line}, end_line={end_line}, total={total_lines}). "
            f"Returning original content."
        )
        return content

    if end_line > total_lines:
        logger.warning(
            f"end_line ({end_line}) exceeds total lines ({total_lines}). Adjusting to total lines."
        )

    filtered = "\n".join(lines[start_idx:end_idx])

    # Safety check: if filtered content is too short, return original
    # (prevents LLM mistakes from destroying content)
    # Note: min_ratio is low because navigation/footer can be much longer than article
    min_chars = 200
    min_ratio = 0.03  # At least 3% of original must remain
    if len(filtered) < min_chars or len(filtered) < len(content) * min_ratio:
        logger.warning(
            f"Content extraction too aggressive "
            f"(original={len(content)}, filtered={len(filtered)}, "
            f"start_line={start_line}, end_line={end_line}). "
            f"Returning original content."
        )
        return content

    return filtered


class ContentProcessor:
    """Service for processing entry content (filtering + summarization)."""

    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        target_language: str = "",
        trace_id: str | None = None,
        trace_name: str | None = None,
        max_content_chars: int = 500000,
        heartbeat_callback: Callable[[str], None] | None = None,
    ):
        """
        Initialize the content processor.

        Parameters
        ----------
        api_key : str
            API key for LLM service.
        base_url : str | None
            Base URL for LLM API (None for OpenAI direct).
        model : str
            Model name to use.
        target_language : str, optional
            Target language code for summaries (default: "" = original language).
        trace_id : str | None, optional
            Trace ID for Langfuse (default: None).
        trace_name : str | None, optional
            Trace name for Langfuse (default: None).
        max_content_chars : int, optional
            Max characters for LLM input, 0 for no limit (default: 500000).
        heartbeat_callback : Callable[[str], None] | None, optional
            Callback for sending heartbeats during processing (default: None).
        """
        self.target_language = target_language
        self.trace_id = trace_id
        self.max_content_chars = max_content_chars
        self._heartbeat = heartbeat_callback

        # Create LLM with Langfuse metadata
        # See: https://docs.litellm.ai/docs/observability/langfuse_integration
        extra_body: dict | None = None
        if trace_id or trace_name:
            metadata: dict = {}
            if trace_id:
                metadata["trace_id"] = trace_id
            if trace_name:
                metadata["trace_name"] = trace_name
                metadata["generation_name"] = "distillation"
            extra_body = {"metadata": metadata}

        llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=SecretStr(api_key),
            extra_body=extra_body,
        )
        self._chain = create_content_processing_chain(llm)
        self._batch_chain = create_batch_content_processing_chain(llm)

        # Initialize Langfuse client for recording filtering results
        self._langfuse = get_client() if trace_id else None

    def _send_heartbeat(self, message: str) -> None:
        """
        Send heartbeat if callback is configured.

        Parameters
        ----------
        message : str
            Heartbeat message for progress tracking.
        """
        if self._heartbeat:
            try:
                self._heartbeat(message)
            except Exception as e:
                logger.debug(
                    f"Heartbeat callback failed: {e}",
                    message=message,
                    error_type=type(e).__name__,
                )

    def _get_language_instruction(self) -> str:
        """
        Get language instruction for the prompt.

        Returns
        -------
        str
            Language instruction string.
        """
        if self.target_language:
            lang_name = LANGUAGE_NAMES.get(self.target_language, self.target_language)
            return lang_name
        return "the same language as the original entry"

    def _record_filtering_result(
        self,
        entry_id: str,
        original_content: str,
        filtered_content: str,
        start_line: int,
        end_line: int,
    ) -> None:
        """
        Record filtering result to Langfuse for LLM-as-a-Judge evaluation.

        Creates a separate trace per entry for cleaner evaluation.

        Parameters
        ----------
        entry_id : str
            Entry ID being processed.
        original_content : str
            Original content before filtering.
        filtered_content : str
            Content after filtering.
        start_line : int
            First line of main content (1-indexed).
        end_line : int
            Last line of main content (1-indexed).
        """
        if not self._langfuse:
            return

        total_lines = len(original_content.split("\n"))

        # Generate deterministic per-entry trace_id
        entry_trace_id = generate_entry_trace_id(entry_id, self.trace_id)

        try:
            # Create a separate trace per entry
            with self._langfuse.start_as_current_observation(
                as_type="span",
                name="filtering-result",
                trace_context={"trace_id": entry_trace_id},
                input={"original_content": original_content},
                metadata={
                    "entry_id": entry_id,
                    "batch_trace_id": self.trace_id,
                },
            ) as span:
                # Update trace name (entry_id is in metadata for identification)
                span.update_trace(name="distillation-eval")
                span.update(
                    output={
                        "filtered_content": filtered_content,
                        "main_content_start_line": start_line,
                        "main_content_end_line": end_line,
                        "total_lines": total_lines,
                    }
                )
        except Exception as e:
            logger.warning(
                f"Failed to record filtering result to Langfuse: {e}",
                entry_id=entry_id,
                error_type=type(e).__name__,
            )

    async def process_entry(self, entry: EntryToProcess) -> ProcessedEntry:
        """
        Process a single entry: filter content and generate summary.

        Parameters
        ----------
        entry : EntryToProcess
            Entry to process.

        Returns
        -------
        ProcessedEntry
            Processed entry with summary and filtered content.
        """
        content = entry.full_content.strip()
        if not content:
            logger.warning("Empty content for entry", entry_id=entry.entry_id)
            return ProcessedEntry(
                entry_id=entry.entry_id,
                summary="",
                filtered_content="",
            )

        # Add line numbers for LLM
        numbered_content = _add_line_numbers(content)

        # Truncate if too long (to fit in context window)
        truncated = False
        if self.max_content_chars > 0 and len(numbered_content) > self.max_content_chars:
            numbered_content = numbered_content[: self.max_content_chars] + "\n... (truncated)"
            truncated = True

        language = self._get_language_instruction()

        total_lines = len(content.split("\n"))

        try:
            result: ContentProcessingLLMOutput = await self._chain.ainvoke(
                {
                    "language": language,
                    "title": entry.title,
                    "content": numbered_content,
                }
            )

            # Extract main content using start/end line numbers
            # If content was truncated, use total_lines as end (LLM didn't see the real end)
            start_line = result.main_content_start_line
            end_line = total_lines if truncated else result.main_content_end_line
            filtered_content = _extract_main_content(content, start_line, end_line)

            if truncated:
                logger.info(
                    "Processed entry (truncated)",
                    entry_id=entry.entry_id,
                    start_line=start_line,
                    end_line=total_lines,
                    llm_end_line=result.main_content_end_line,
                )
            else:
                logger.info(
                    "Processed entry",
                    entry_id=entry.entry_id,
                    start_line=start_line,
                    end_line=end_line,
                    total_lines=total_lines,
                )

            # Record filtering result to Langfuse for evaluation
            self._record_filtering_result(
                entry_id=entry.entry_id,
                original_content=content,
                filtered_content=filtered_content,
                start_line=start_line,
                end_line=end_line,
            )

            return ProcessedEntry(
                entry_id=entry.entry_id,
                summary=result.summary.strip(),
                filtered_content=filtered_content,
                start_line=start_line,
                end_line=end_line,
            )

        except Exception as e:
            logger.error(
                f"Error processing entry: {e}",
                entry_id=entry.entry_id,
                error_type=type(e).__name__,
            )
            return ProcessedEntry(
                entry_id=entry.entry_id,
                summary="",
                filtered_content=content,  # Return original on error
                start_line=1,
                end_line=total_lines,
            )

    async def process_entries(
        self,
        entries: list[EntryToProcess],
    ) -> list[ProcessedEntry]:
        """
        Process multiple entries sequentially.

        Parameters
        ----------
        entries : list[EntryToProcess]
            List of entries to process.

        Returns
        -------
        list[ProcessedEntry]
            List of processed entries.
        """
        if not entries:
            logger.info("No entries to process")
            return []

        # Filter out entries without content
        entries_with_content = [e for e in entries if e.full_content.strip()]

        if not entries_with_content:
            logger.info("No entries with content to process")
            return []

        total = len(entries_with_content)
        logger.info("Processing entries", total=total)

        results: list[ProcessedEntry] = []

        for i, entry in enumerate(entries_with_content):
            self._send_heartbeat(f"Processing entry {i + 1}/{total}: {entry.entry_id}")
            logger.debug("Processing entry", index=i + 1, total=total, entry_id=entry.entry_id)
            result = await self.process_entry(entry)
            results.append(result)

        success_count = sum(1 for r in results if r.summary)
        self._send_heartbeat(f"Processing completed: {success_count}/{total} successful")
        logger.info("Processing completed", success_count=success_count, total=total)

        return results

    async def process_entries_parallel(
        self,
        entries: list[EntryToProcess],
        max_concurrency: int = 5,
    ) -> list[ProcessedEntry]:
        """
        Process multiple entries with parallel API calls.

        Each entry gets its own individual prompt (same as process_entry),
        but API calls are made in parallel using LangChain's abatch method.
        This provides the same accuracy as sequential processing with better throughput.

        Parameters
        ----------
        entries : list[EntryToProcess]
            List of entries to process.
        max_concurrency : int, optional
            Maximum number of concurrent API calls (default: 5).

        Returns
        -------
        list[ProcessedEntry]
            List of processed entries.
        """
        if not entries:
            logger.info("No entries to process")
            return []

        # Filter out entries without content
        entries_with_content = [e for e in entries if e.full_content.strip()]

        if not entries_with_content:
            logger.info("No entries with content to process")
            return []

        total = len(entries_with_content)
        logger.info("Processing entries in parallel", total=total, max_concurrency=max_concurrency)
        self._send_heartbeat(f"Starting parallel processing: {total} entries")

        language = self._get_language_instruction()

        # Prepare inputs for batch processing
        inputs: list[dict] = []
        truncated_entries: set[str] = set()  # Track which entries were truncated
        entry_line_counts: dict[str, int] = {}  # Track total lines per entry
        for entry in entries_with_content:
            content = entry.full_content.strip()
            total_lines = len(content.split("\n"))
            entry_line_counts[str(entry.entry_id)] = total_lines
            numbered_content = _add_line_numbers(content)

            # Truncate if too long
            if self.max_content_chars > 0 and len(numbered_content) > self.max_content_chars:
                numbered_content = numbered_content[: self.max_content_chars] + "\n... (truncated)"
                truncated_entries.add(entry.entry_id)

            inputs.append(
                {
                    "language": language,
                    "title": entry.title,
                    "content": numbered_content,
                }
            )

        try:
            self._send_heartbeat(f"Calling LLM API for {total} entries...")
            # Use LangChain abatch for parallel async API calls
            results: list[ContentProcessingLLMOutput] = await self._chain.abatch(
                inputs,
                config={"max_concurrency": max_concurrency},
            )
            self._send_heartbeat(f"LLM API completed, processing {len(results)} results...")

            # Process results
            processed_results: list[ProcessedEntry] = []

            for entry, result in zip(entries_with_content, results, strict=True):
                # Extract main content using start/end line numbers
                original_content = entry.full_content
                truncated = entry.entry_id in truncated_entries
                total_lines = entry_line_counts.get(str(entry.entry_id), 0)
                start_line = result.main_content_start_line
                end_line = total_lines if truncated else result.main_content_end_line
                filtered_content = _extract_main_content(
                    original_content,
                    start_line,
                    end_line,
                )

                if truncated:
                    logger.info(
                        "Processed entry (truncated)",
                        entry_id=entry.entry_id,
                        start_line=start_line,
                        end_line=total_lines,
                        llm_end_line=result.main_content_end_line,
                    )
                else:
                    logger.info(
                        "Processed entry",
                        entry_id=entry.entry_id,
                        start_line=start_line,
                        end_line=end_line,
                        total_lines=total_lines,
                    )

                # Record filtering result to Langfuse for evaluation
                self._record_filtering_result(
                    entry_id=entry.entry_id,
                    original_content=original_content,
                    filtered_content=filtered_content,
                    start_line=start_line,
                    end_line=end_line,
                )

                processed_results.append(
                    ProcessedEntry(
                        entry_id=entry.entry_id,
                        summary=result.summary.strip(),
                        filtered_content=filtered_content,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )

            success_count = sum(1 for r in processed_results if r.summary)
            self._send_heartbeat(
                f"Parallel processing completed: {success_count}/{total} successful"
            )
            logger.info(
                "Parallel processing completed",
                success_count=success_count,
                total=total,
            )

            return processed_results

        except Exception as e:
            logger.error(
                "Error in parallel content processing",
                error=str(e),
                error_type=type(e).__name__,
            )
            # Re-raise to let Temporal handle retry
            raise

    def _format_entry_for_batch(self, entry: EntryToProcess) -> tuple[str, str, int, bool]:
        """
        Format a single entry for batch processing.

        Parameters
        ----------
        entry : EntryToProcess
            Entry to format.

        Returns
        -------
        tuple[str, str, int, bool]
            Tuple of (entry_id, formatted_text, total_lines, truncated).
        """
        content = entry.full_content.strip()
        lines = content.split("\n")
        total_lines = len(lines)
        numbered_content = _add_line_numbers(content)

        # Truncate if too long (shorter per-entry limit for batches)
        # Use half of max_content_chars for batch processing, or 30000 if no limit set
        batch_max_chars = self.max_content_chars // 2 if self.max_content_chars > 0 else 30000
        truncated = False
        if len(numbered_content) > batch_max_chars:
            numbered_content = numbered_content[:batch_max_chars] + "\n... (truncated)"
            truncated = True

        # Include total lines in header for LLM to validate its output
        formatted = (
            f"=== ENTRY_ID: {entry.entry_id} (TOTAL_LINES: {total_lines}) ===\n"
            f"TITLE: {entry.title}\n"
            f"CONTENT:\n{numbered_content}\n"
            f"=== END ENTRY {entry.entry_id} (last line: {total_lines}) ===\n"
        )
        if truncated:
            logger.warning(
                f"Entry {entry.entry_id} truncated for batch (original {total_lines} lines)"
            )
        return str(entry.entry_id), formatted, total_lines, truncated

    async def process_entries_batch(
        self,
        entries: list[EntryToProcess],
    ) -> list[ProcessedEntry]:
        """
        Process multiple entries in a single LLM call.

        Parameters
        ----------
        entries : list[EntryToProcess]
            List of entries to process (recommended: 5 or fewer).

        Returns
        -------
        list[ProcessedEntry]
            List of processed entries.
        """
        if not entries:
            logger.info("No entries to process")
            return []

        # Filter out entries without content
        entries_with_content = [e for e in entries if e.full_content.strip()]

        if not entries_with_content:
            logger.info("No entries with content to process")
            return []

        total = len(entries_with_content)
        logger.info("Batch processing entries in single LLM call", total=total)
        self._send_heartbeat(f"Starting batch processing: {total} entries")

        # Build entry ID -> entry mapping for result lookup
        entry_map: dict[str, EntryToProcess] = {}
        entry_line_counts: dict[str, int] = {}  # Track total lines per entry
        truncated_entries: set[str] = set()  # Track which entries were truncated
        formatted_entries: list[str] = []

        for entry in entries_with_content:
            entry_id, formatted, total_lines, truncated = self._format_entry_for_batch(entry)
            entry_map[entry_id] = entry
            entry_line_counts[entry_id] = total_lines
            if truncated:
                truncated_entries.add(entry_id)
            formatted_entries.append(formatted)

        entries_text = "\n".join(formatted_entries)
        language = self._get_language_instruction()

        try:
            self._send_heartbeat(f"Calling LLM API for batch of {total} entries...")
            result: BatchContentProcessingOutput = await self._batch_chain.ainvoke(
                {
                    "language": language,
                    "entry_count": total,
                    "entries": entries_text,
                }
            )
            self._send_heartbeat("LLM API completed, processing results...")

            # Process results and match to entries
            processed_results: list[ProcessedEntry] = []

            for entry_result in result.results:
                entry_id = entry_result.entry_id
                entry = entry_map.get(entry_id)

                if not entry:
                    logger.warning("Unknown entry_id in result", entry_id=entry_id)
                    continue

                # Validate LLM output against actual line count
                total_lines = entry_line_counts.get(entry_id, 0)
                start_line = entry_result.main_content_start_line
                # If content was truncated, use total_lines as end (LLM didn't see the end)
                truncated = entry_id in truncated_entries
                end_line = total_lines if truncated else entry_result.main_content_end_line
                original_content = entry.full_content

                # Validate range
                if start_line > end_line or end_line > total_lines:
                    logger.warning(
                        f"Entry {entry_id}: LLM returned invalid line range "
                        f"(start={start_line}, end={end_line}, total={total_lines}). "
                        f"Using original content."
                    )
                    filtered_content = original_content
                else:
                    # Extract main content
                    filtered_content = _extract_main_content(
                        original_content,
                        start_line,
                        end_line,
                    )

                if truncated:
                    logger.info(
                        "Processed entry (truncated)",
                        entry_id=entry_id,
                        start_line=start_line,
                        end_line=total_lines,
                        llm_end_line=entry_result.main_content_end_line,
                    )
                else:
                    logger.info(
                        "Processed entry",
                        entry_id=entry_id,
                        start_line=start_line,
                        end_line=end_line,
                        total_lines=total_lines,
                    )

                # Record filtering result to Langfuse for evaluation
                self._record_filtering_result(
                    entry_id=entry.entry_id,
                    original_content=original_content,
                    filtered_content=filtered_content,
                    start_line=start_line,
                    end_line=end_line,
                )

                processed_results.append(
                    ProcessedEntry(
                        entry_id=entry.entry_id,
                        summary=entry_result.summary.strip(),
                        filtered_content=filtered_content,
                        start_line=start_line,
                        end_line=end_line,
                    )
                )

            # Check for missing results and add fallback
            result_ids = {r.entry_id for r in result.results}
            for entry_id, entry in entry_map.items():
                if entry_id not in result_ids:
                    logger.warning("No result returned for entry", entry_id=entry_id)
                    total_lines = entry_line_counts.get(entry_id, 0)
                    processed_results.append(
                        ProcessedEntry(
                            entry_id=entry.entry_id,
                            summary="",
                            filtered_content=entry.full_content,
                            start_line=1,
                            end_line=total_lines,
                        )
                    )

            success_count = sum(1 for r in processed_results if r.summary)
            self._send_heartbeat(f"Batch processing completed: {success_count}/{total} successful")
            logger.info(
                "Batch processing completed",
                success_count=success_count,
                total=total,
            )

            return processed_results

        except Exception as e:
            logger.error(
                f"Error in batch processing: {e}",
                error_type=type(e).__name__,
            )
            # Re-raise to let Temporal handle retry
            raise
