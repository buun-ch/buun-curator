"use client";

import * as React from "react";

import {
  useWorkflowStore,
  selectWorkflowById,
} from "@/stores/workflow-store";
import type { FetchEntryLinksProgress } from "@/lib/temporal";
/** Debounce delay in milliseconds. */
const DEBOUNCE_DELAY = 1000;

interface UseLinkEnrichmentOptions {
  /** Entry ID to enrich links for. */
  entryId?: string;
  /** Set of URLs that are already enriched (from context data). */
  enrichedUrls?: Set<string>;
  /** Callback when workflow starts. */
  onWorkflowStart?: (workflowId: string, urls: string[]) => void;
  /** Callback when workflow completes or fails. */
  onWorkflowComplete?: (success: boolean, error?: string) => void;
}

interface UseLinkEnrichmentReturn {
  /** Add a URL to the pending queue. */
  addUrl: (url: string) => void;
  /** URLs currently pending (waiting for debounce). */
  pendingUrls: Set<string>;
  /** URLs currently being fetched. */
  fetchingUrls: Set<string>;
  /** URLs that failed to fetch with error messages. */
  failedUrls: Map<string, string>;
  /** Whether a workflow is currently running. */
  isFetching: boolean;
  /** Current workflow ID if running. */
  workflowId: string | null;
}

/**
 * Hook for managing debounced link enrichment.
 *
 * Collects URLs when "+" is clicked and batches them together
 * after a debounce delay before triggering the workflow.
 */
export function useLinkEnrichment({
  entryId,
  enrichedUrls,
  onWorkflowStart,
  onWorkflowComplete,
}: UseLinkEnrichmentOptions): UseLinkEnrichmentReturn {
  // Pending URLs waiting for debounce
  const [pendingUrls, setPendingUrls] = React.useState<Set<string>>(new Set());
  // URLs currently being fetched
  const [fetchingUrls, setFetchingUrls] = React.useState<Set<string>>(new Set());
  // URLs that failed to fetch (URL -> error message)
  const [failedUrls, setFailedUrls] = React.useState<Map<string, string>>(
    new Map()
  );
  // Current workflow ID
  const [workflowId, setWorkflowId] = React.useState<string | null>(null);
  // Debounce timer ref
  const timerRef = React.useRef<NodeJS.Timeout | null>(null);
  // Ref for pending URLs (to access in timer callback without stale closure)
  const pendingUrlsRef = React.useRef<Set<string>>(new Set());

  // Get workflow from store (SSE-updated)
  const workflow = useWorkflowStore(
    workflowId ? selectWorkflowById(workflowId) : () => null
  );
  // Ref to track current entryId for async operations
  const entryIdRef = React.useRef(entryId);

  // Refs for callbacks to avoid stale closures and dependency issues
  const onWorkflowStartRef = React.useRef(onWorkflowStart);
  const onWorkflowCompleteRef = React.useRef(onWorkflowComplete);

  // Update callback refs
  React.useEffect(() => {
    onWorkflowStartRef.current = onWorkflowStart;
  }, [onWorkflowStart]);

  React.useEffect(() => {
    onWorkflowCompleteRef.current = onWorkflowComplete;
  }, [onWorkflowComplete]);

  // Update entryId ref
  React.useEffect(() => {
    entryIdRef.current = entryId;
  }, [entryId]);

  // Reset state when entry changes
  React.useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setPendingUrls(new Set());
    setFetchingUrls(new Set());
    setFailedUrls(new Map());
    setWorkflowId(null);
    pendingUrlsRef.current = new Set();
  }, [entryId]);

  // Watch workflow status via SSE
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

    if (workflow.status === "completed" || workflow.status === "error") {
      const success = workflow.status === "completed";

      // Extract failed URLs from workflow progress
      // Cast to unknown first since WorkflowProgressNode doesn't include workflow-specific fields
      const progress = workflow as unknown as FetchEntryLinksProgress;
      const newFailedUrls = new Map<string, string>();
      if (progress.urlProgress) {
        for (const [url, state] of Object.entries(progress.urlProgress)) {
          if (state.status === "error") {
            newFailedUrls.set(url, state.error || "Failed to fetch content");
          }
        }
      }

      // Defer state updates to avoid synchronous setState in effect
      queueMicrotask(() => {
        setFetchingUrls(new Set());
        setWorkflowId(null);
        // Update failed URLs (merge with existing)
        if (newFailedUrls.size > 0) {
          setFailedUrls((prev) => {
            const merged = new Map(prev);
            for (const [url, error] of newFailedUrls) {
              merged.set(url, error);
            }
            return merged;
          });
        }
        onWorkflowCompleteRef.current?.(success, success ? undefined : "Workflow failed");
      });
    }
  }, [workflow, workflowId]);

  // Remove URLs from fetching when they become enriched
  React.useEffect(() => {
    if (!enrichedUrls || enrichedUrls.size === 0) return;

    setFetchingUrls((prev) => {
      const stillFetching = new Set<string>();
      for (const url of prev) {
        if (!enrichedUrls.has(url)) {
          stillFetching.add(url);
        }
      }
      // Only update if something changed
      if (stillFetching.size !== prev.size) {
        return stillFetching;
      }
      return prev;
    });
  }, [enrichedUrls]);

  // Cleanup on unmount
  React.useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
    };
  }, []);

  // Start the workflow with collected URLs
  const startWorkflow = React.useCallback(async (urls: string[]) => {
    const currentEntryId = entryIdRef.current;
    if (!currentEntryId || urls.length === 0) return;

    // Clear pending immediately (before async operations)
    setPendingUrls(new Set());
    pendingUrlsRef.current = new Set();

    // Move to fetching
    setFetchingUrls(new Set(urls));

    try {
      const response = await fetch(`/api/entries/${currentEntryId}/fetch-links`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Failed to start workflow");
      }

      const data = await response.json();
      setWorkflowId(data.workflowId);
      onWorkflowStartRef.current?.(data.workflowId, urls);
      // SSE will notify when workflow completes via useWorkflowStore
    } catch (error) {
      console.error("Failed to start fetch links workflow:", error);
      // Clear fetching on error
      setFetchingUrls(new Set());
      onWorkflowCompleteRef.current?.(false, error instanceof Error ? error.message : "Unknown error");
    }
  }, []);

  // Add URL to pending queue with debounce
  const addUrl = React.useCallback((url: string) => {
    if (!entryId) return;

    // Clear error state for this URL if retrying
    setFailedUrls((prev) => {
      if (prev.has(url)) {
        const next = new Map(prev);
        next.delete(url);
        return next;
      }
      return prev;
    });

    // Update both state and ref
    setPendingUrls((prev) => {
      const next = new Set(prev);
      next.add(url);
      pendingUrlsRef.current = next;
      return next;
    });

    // Clear existing timer
    if (timerRef.current) {
      clearTimeout(timerRef.current);
    }

    // Set new timer - read from ref to avoid stale closure
    timerRef.current = setTimeout(() => {
      const currentPending = pendingUrlsRef.current;
      if (currentPending.size > 0) {
        startWorkflow(Array.from(currentPending));
      }
    }, DEBOUNCE_DELAY);
  }, [entryId, startWorkflow]);

  return {
    addUrl,
    pendingUrls,
    fetchingUrls,
    failedUrls,
    isFetching: fetchingUrls.size > 0,
    workflowId,
  };
}
