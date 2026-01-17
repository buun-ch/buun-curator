"use client";

import { useState, useCallback, useEffect, useRef } from "react";

import type { LanguageMode } from "@/lib/types";
import {
  useWorkflowStore,
  selectWorkflowById,
} from "@/stores/workflow-store";
interface UseTranslationOptions {
  /** The entry ID to translate. */
  entryId?: string;
  /** Whether translation content already exists. */
  hasTranslation: boolean;
  /** Current language mode. */
  languageMode: LanguageMode;
  /** Callback when translation completes and entry should be refetched. */
  onTranslationComplete?: (entryId: string) => void;
}

interface UseTranslationReturn {
  /** Whether translation is currently in progress. */
  isTranslating: boolean;
  /** Trigger a new translation (or re-translation). */
  triggerTranslation: () => Promise<void>;
}

/**
 * Hook for managing translation state and triggering translations.
 *
 * Uses SSE-based workflow tracking instead of polling.
 *
 * Note: This hook's state persists across entryId changes.
 * The parent component should reset languageMode when entry changes
 * to prevent auto-triggering for the new entry.
 */
export function useTranslation({
  entryId,
  hasTranslation,
  languageMode,
  onTranslationComplete,
}: UseTranslationOptions): UseTranslationReturn {
  const [isTranslating, setIsTranslating] = useState(false);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [triggeredEntryId, setTriggeredEntryId] = useState<string | null>(null);

  // Store the entryId that was being translated when workflow started
  const translatingEntryIdRef = useRef<string | null>(null);

  // Get workflow from store (SSE-updated)
  const workflow = useWorkflowStore(
    workflowId ? selectWorkflowById(workflowId) : () => null
  );

  // Get action to register immediate translating state
  const addTranslatingEntry = useWorkflowStore(
    (state) => state.addTranslatingEntry
  );

  // Check if we've already triggered for this entry
  const hasTriggeredForCurrentEntry = triggeredEntryId === entryId;

  // Trigger translation
  const triggerTranslation = useCallback(async () => {
    if (!entryId) return;

    setIsTranslating(true);
    setWorkflowId(null);
    setTriggeredEntryId(entryId);
    translatingEntryIdRef.current = entryId;

    // Register for immediate UI feedback (before SSE kicks in)
    addTranslatingEntry(entryId);

    try {
      const response = await fetch(`/api/entries/${entryId}/translate`, {
        method: "POST",
      });
      if (response.ok) {
        const data = await response.json();
        setWorkflowId(data.workflowId);
      } else {
        setIsTranslating(false);
        translatingEntryIdRef.current = null;
      }
    } catch (error) {
      console.error("Failed to start translation:", error);
      setIsTranslating(false);
      translatingEntryIdRef.current = null;
    }
  }, [entryId, addTranslatingEntry]);

  // Auto-trigger translation when mode requires it and no translation exists
  useEffect(() => {
    // Don't auto-trigger if:
    // - Not in translated/both mode
    // - No entry ID
    // - Already has translation
    // - Already triggered for this entry
    if (
      (languageMode !== "translated" && languageMode !== "both") ||
      !entryId ||
      hasTranslation ||
      hasTriggeredForCurrentEntry
    ) {
      return;
    }
    // Defer to avoid synchronous setState in effect
    const timeoutId = setTimeout(() => {
      triggerTranslation();
    }, 0);
    return () => clearTimeout(timeoutId);
  }, [languageMode, entryId, hasTranslation, hasTriggeredForCurrentEntry, triggerTranslation]);

  // Watch workflow status via SSE (replaces polling)
  // Use ref to track previous status and avoid duplicate processing
  const prevStatusRef = useRef<string | null>(null);

  useEffect(() => {
    if (!workflow || !workflowId) {
      prevStatusRef.current = null;
      return;
    }

    // Skip if status hasn't changed
    if (workflow.status === prevStatusRef.current) return;
    prevStatusRef.current = workflow.status;

    if (workflow.status === "completed" || workflow.status === "error") {
      const completedEntryId = translatingEntryIdRef.current;

      // Defer state updates to avoid synchronous setState in effect
      queueMicrotask(() => {
        setIsTranslating(false);
        setWorkflowId(null);
        translatingEntryIdRef.current = null;

        // Call completion callback only on success
        if (workflow.status === "completed" && completedEntryId) {
          onTranslationComplete?.(completedEntryId);
        }
      });
    }
  }, [workflow, workflowId, onTranslationComplete]);

  // Reset isTranslating when entry changes (to avoid showing spinner for new entry)
  // This is safe because it's tied to entryId, not just any prop change
  const currentIsTranslating = triggeredEntryId === entryId ? isTranslating : false;

  return {
    isTranslating: currentIsTranslating,
    triggerTranslation,
  };
}
