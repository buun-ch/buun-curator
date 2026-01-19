"use client";

import * as React from "react";

import { useWorkflowStore, selectWorkflowById } from "@/stores/workflow-store";

import type { EntryContext } from "../types";

interface UseContextDataOptions {
  entryId?: string;
  open: boolean;
}

interface UseContextDataResult {
  data: EntryContext | null;
  loading: boolean;
  error: string | null;
  extracting: boolean;
  fetchContext: () => Promise<EntryContext | null>;
  startExtraction: () => Promise<void>;
}

/**
 * Hook for managing context data fetching and extraction.
 *
 * Uses SSE-based workflow tracking instead of polling.
 *
 * @param options - Hook options
 * @returns Context data state and actions
 */
export function useContextData({
  entryId,
  open,
}: UseContextDataOptions): UseContextDataResult {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [data, setData] = React.useState<EntryContext | null>(null);
  const [extracting, setExtracting] = React.useState(false);
  const [workflowId, setWorkflowId] = React.useState<string | null>(null);

  // Get workflow from store (SSE-updated)
  const workflow = useWorkflowStore(
    workflowId ? selectWorkflowById(workflowId) : () => null,
  );

  // Fetch context data
  const fetchContext = React.useCallback(async () => {
    if (!entryId) {
      setData(null);
      return null;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/entries/${entryId}/context`);
      if (!response.ok) {
        throw new Error(`Failed to fetch context: ${response.statusText}`);
      }
      const result = await response.json();
      setData(result);
      return result as EntryContext;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      return null;
    } finally {
      setLoading(false);
    }
  }, [entryId]);

  // Start context collection workflow
  const startExtraction = React.useCallback(async () => {
    if (!entryId || extracting) return;

    setExtracting(true);
    setError(null);

    try {
      const response = await fetch(`/api/entries/${entryId}/context/collect`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(`Failed to start collection: ${response.statusText}`);
      }
      const result = await response.json();
      setWorkflowId(result.workflowId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setExtracting(false);
    }
  }, [entryId, extracting]);

  // Watch workflow status via SSE (replaces polling)
  // Use ref to track previous status and avoid duplicate processing
  const prevStatusRef = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (!workflow || !workflowId) {
      prevStatusRef.current = null;
      return;
    }

    // Skip if status hasn't changed
    if (workflow.status === prevStatusRef.current) return;
    prevStatusRef.current = workflow.status;

    if (workflow.status === "completed") {
      // Defer state updates to avoid synchronous setState in effect
      queueMicrotask(() => {
        setExtracting(false);
        setWorkflowId(null);
        // Refetch context data
        fetchContext();
      });
    } else if (workflow.status === "error") {
      queueMicrotask(() => {
        setExtracting(false);
        setWorkflowId(null);
        setError("Extraction failed");
      });
    }
  }, [workflow, workflowId, fetchContext]);

  // Fetch existing context data when panel opens (without auto-starting extraction)
  React.useEffect(() => {
    if (!open || !entryId) return;
    fetchContext();
  }, [open, entryId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    data,
    loading,
    error,
    extracting,
    fetchContext,
    startExtraction,
  };
}
