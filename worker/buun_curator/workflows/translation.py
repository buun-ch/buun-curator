"""
Translation Workflow.

Unified workflow for translating entries using DeepL or Microsoft Translator API.
"""

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from buun_curator.activities import (
        get_app_settings,
        get_entries_for_translation,
        save_translations,
    )
    from buun_curator.activities.deepl_translate import deepl_translate_entries
    from buun_curator.activities.ms_translate import ms_translate_entries
    from buun_curator.models import (
        EntryProgressState,
        GetAppSettingsInput,
        GetAppSettingsOutput,
        GetEntriesForTranslationInput,
        GetEntriesForTranslationOutput,
        SaveTranslationsInput,
        SaveTranslationsOutput,
        TranslateEntriesInput,
        TranslateEntriesOutput,
        TranslationProgress,
    )
    from buun_curator.models.workflow_io import TranslationInput, TranslationResult
    from buun_curator.utils.date import workflow_now_iso
    from buun_curator.workflows.progress_mixin import ProgressNotificationMixin


@workflow.defn
class TranslationWorkflow(ProgressNotificationMixin):
    """
    Unified workflow for translating entries.

    Supports multiple translation providers:
    - "deepl": DeepL API
    - "microsoft": Microsoft Translator API

    Can be used:
    - Independently to translate specific entries
    - To batch process all untranslated entries
    """

    def __init__(self) -> None:
        """Initialize workflow progress state."""
        self._progress = TranslationProgress()

    @workflow.query
    def get_progress(self) -> TranslationProgress:
        """Return current workflow progress for Temporal Query."""
        return self._progress

    def _update_entry_status(self, entry_id: str, status: str, error: str = "") -> None:
        """Update status for a specific entry."""
        now = workflow_now_iso()
        if entry_id in self._progress.entry_progress:
            self._progress.entry_progress[entry_id].status = status
            self._progress.entry_progress[entry_id].changed_at = now
            if error:
                self._progress.entry_progress[entry_id].error = error
        self._progress.updated_at = now

    @workflow.run
    async def run(
        self,
        input: TranslationInput,
    ) -> TranslationResult:
        """
        Run the translation workflow.

        Parameters
        ----------
        input : TranslationInput
            Workflow input containing entry IDs and provider.

        Returns
        -------
        TranslationResult
            Result containing workflow statistics.
        """
        # Extract input fields for convenience
        entry_ids = input.entry_ids
        provider = input.provider

        wf_info = workflow.info()

        # Initialize progress state
        now = workflow_now_iso()
        self._progress.workflow_id = wf_info.workflow_id
        self._progress.provider = provider
        self._progress.started_at = now
        self._progress.updated_at = now
        self._progress.status = "running"
        self._progress.current_step = "initializing"
        self._progress.message = "Starting translation..."

        provider_label = "DeepL" if provider == "deepl" else "Microsoft"
        workflow.logger.info(
            "TranslationWorkflow start",
            extra={
                "workflow_id": wf_info.workflow_id,
                "provider": provider,
                "entry_ids": len(entry_ids) if entry_ids else "auto",
            },
        )

        # 0. Get app settings (target language)
        settings_result: GetAppSettingsOutput = await workflow.execute_activity(
            get_app_settings,
            GetAppSettingsInput(),
            start_to_close_timeout=timedelta(minutes=1),
        )
        target_language = settings_result.target_language
        workflow.logger.info("Target language", extra={"target_language": target_language})

        if not target_language:
            workflow.logger.info(
                "No target language configured, skipping translation",
                extra={"workflow_id": wf_info.workflow_id},
            )

            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "No target language configured"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return TranslationResult(
                status="no_target_language",
                provider=provider,
                total_entries=0,
                translations_created=0,
            )

        # 1. Get entries to translate
        get_result: GetEntriesForTranslationOutput = await workflow.execute_activity(
            get_entries_for_translation,
            GetEntriesForTranslationInput(entry_ids=entry_ids),
            start_to_close_timeout=timedelta(minutes=2),
        )
        entries = get_result.entries

        if not entries:
            workflow.logger.info(
                "No entries to translate",
                extra={"workflow_id": wf_info.workflow_id},
            )

            self._progress.status = "completed"
            self._progress.current_step = "done"
            self._progress.message = "No entries to translate"
            self._progress.updated_at = workflow_now_iso()
            await self._notify_update()

            return TranslationResult(
                status="no_entries",
                provider=provider,
                total_entries=0,
                translations_created=0,
            )

        workflow.logger.info("Found entries to translate", extra={"entries": len(entries)})

        # Initialize entry progress tracking
        now = workflow_now_iso()
        self._progress.total_entries = len(entries)
        for entry in entries:
            entry_id = entry.get("entry_id", "")
            title = entry.get("title", "")
            self._progress.entry_progress[entry_id] = EntryProgressState(
                entry_id=entry_id,
                title=title,
                status="pending",
                changed_at=now,
            )
        self._progress.updated_at = now
        await self._notify_update()

        # 2. Translate entries using selected provider
        self._progress.current_step = "translate"
        self._progress.message = f"Translating {len(entries)} entries with {provider_label}..."
        for entry_id in self._progress.entry_progress:
            self._update_entry_status(entry_id, "translating")
        await self._notify_update()

        # Select activity based on provider
        translate_activity = (
            deepl_translate_entries if provider == "deepl" else ms_translate_entries
        )

        translate_result: TranslateEntriesOutput = await workflow.execute_activity(
            translate_activity,
            TranslateEntriesInput(
                entries=entries,
                batch_size=1,  # Process one at a time
                target_language=target_language,
            ),
            start_to_close_timeout=timedelta(minutes=30),
            heartbeat_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=2,
                initial_interval=timedelta(seconds=10),
            ),
        )
        translations = translate_result.translations

        # 3. Save translations
        translations_created = 0
        if translations:
            save_result: SaveTranslationsOutput = await workflow.execute_activity(
                save_translations,
                SaveTranslationsInput(translations=translations),
                start_to_close_timeout=timedelta(minutes=2),
            )
            translations_created = save_result.saved_count

            # Mark translated entries as completed
            translated_ids = {t.get("entry_id") for t in translations}
            for entry_id in self._progress.entry_progress:
                if entry_id in translated_ids:
                    self._update_entry_status(entry_id, "completed")
                else:
                    self._update_entry_status(entry_id, "error")
            self._progress.entries_translated = translations_created
            await self._notify_update()

        workflow.logger.info(
            "TranslationWorkflow end",
            extra={
                "workflow_id": wf_info.workflow_id,
                "translations_created": translations_created,
                "total_entries": len(entries),
            },
        )

        # Update final progress state
        self._progress.status = "completed"
        self._progress.current_step = "done"
        self._progress.message = f"Completed: {translations_created} translations"
        self._progress.updated_at = workflow_now_iso()
        await self._notify_update()

        return TranslationResult(
            status="completed",
            provider=provider,
            total_entries=len(entries),
            translations_created=translations_created,
        )
