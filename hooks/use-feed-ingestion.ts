/**
 * Hook for triggering all-feeds ingestion workflow.
 *
 * Starts a Temporal workflow to fetch new entries from all feeds.
 * Loading state is derived from the workflow store for accurate
 * real-time status across page refreshes.
 *
 * @module hooks/use-feed-ingestion
 */

"use client";

import * as React from "react";
import {
  useWorkflowStore,
  selectIsWorkflowTypeRunning,
} from "@/stores/workflow-store";
/** Options for the useFeedIngestion hook. */
export interface UseFeedIngestionOptions {
  /** Callback invoked before starting the workflow. */
  onStart?: () => Promise<void>;
  /** Callback invoked after workflow completes. */
  onComplete?: () => Promise<void>;
}

/** Return value from the useFeedIngestion hook. */
export interface UseFeedIngestionReturn {
  /** True while the ingestion workflow is running. */
  isFetchingNew: boolean;
  /** Starts the all-feeds ingestion workflow. */
  handleFetchNew: () => Promise<void>;
}

/**
 * Hook for triggering all-feeds ingestion workflow.
 *
 * Starts the AllFeedsIngestionWorkflow via API. Loading state is
 * derived from the workflow store, which gets updates via SSE.
 *
 * @param options - Hook options with lifecycle callbacks
 * @returns Ingestion state and trigger function
 */
export function useFeedIngestion({
  onStart,
  onComplete,
}: UseFeedIngestionOptions = {}): UseFeedIngestionReturn {
  // Check if AllFeedsIngestion workflow is running via workflow store
  const isWorkflowRunning = useWorkflowStore(
    selectIsWorkflowTypeRunning("AllFeedsIngestion")
  );

  // Local state for API call in progress (before workflow starts)
  const [isStarting, setIsStarting] = React.useState(false);

  // Track if the workflow was initiated by the user (vs background scheduler)
  const userInitiatedRef = React.useRef(false);

  // Combined loading state
  const isFetchingNew = isStarting || isWorkflowRunning;

  // Track previous workflow state to detect completion
  const prevWorkflowRunning = React.useRef(isWorkflowRunning);
  React.useEffect(() => {
    // Detect workflow completion: was running, now not running
    // Only call onComplete if user initiated the workflow (not background scheduler)
    if (prevWorkflowRunning.current && !isWorkflowRunning) {
      if (userInitiatedRef.current) {
        onComplete?.();
        userInitiatedRef.current = false;
      }
    }
    prevWorkflowRunning.current = isWorkflowRunning;
  }, [isWorkflowRunning, onComplete]);

  const handleFetchNew = React.useCallback(async () => {
    userInitiatedRef.current = true;
    setIsStarting(true);
    try {
      // Refresh data before starting workflow
      if (onStart) {
        await onStart();
      }

      const response = await fetch("/api/workflows/ingest", {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Failed to start ingestion workflow");
      }

      // Workflow started - SSE will provide progress updates
      // isWorkflowRunning will become true when SSE receives the update
    } catch (error) {
      console.error("Failed to fetch new entries:", error);
      userInitiatedRef.current = false;
    } finally {
      setIsStarting(false);
    }
  }, [onStart]);

  return {
    isFetchingNew,
    handleFetchNew,
  };
}
