/**
 * Hook for triggering single feed ingestion workflow.
 *
 * Starts a Temporal workflow to fetch new entries from a specific
 * feed. Loading state is derived from the workflow store for accurate
 * real-time status across page refreshes.
 *
 * @module hooks/use-single-feed-ingestion
 */

"use client";

import * as React from "react";
import {
  useWorkflowStore,
  selectIsFeedIngesting,
} from "@/stores/workflow-store";
/** Options for the useSingleFeedIngestion hook. */
export interface UseSingleFeedIngestionOptions {
  /** Feed ID to ingest. */
  feedId?: string;
  /** Feed name for the workflow. */
  feedName?: string;
  /** Feed URL to fetch from. */
  feedUrl?: string;
  /** Enable thumbnail capture (default: true). */
  enableThumbnail?: boolean;
  /** Delay between requests to same domain in seconds (default: 2.0). */
  domainFetchDelay?: number;
  /** Callback invoked before starting the workflow. */
  onStart?: () => Promise<void>;
  /** Callback invoked after workflow completes. */
  onComplete?: () => Promise<void>;
}

/** Return value from the useSingleFeedIngestion hook. */
export interface UseSingleFeedIngestionReturn {
  /** True while the ingestion workflow is running. */
  isIngesting: boolean;
  /** Starts the single feed ingestion workflow. */
  handleIngest: () => Promise<void>;
  /** True if all required feed info is available. */
  canIngest: boolean;
}

/**
 * Hook for triggering single feed ingestion workflow.
 *
 * Starts the SingleFeedIngestionWorkflow via API for a specific
 * feed. Loading state is derived from the workflow store, which
 * gets updates via SSE.
 *
 * @param options - Hook options with feed details and callbacks
 * @returns Ingestion state and trigger function
 */
export function useSingleFeedIngestion({
  feedId,
  feedName,
  feedUrl,
  enableThumbnail = true,
  domainFetchDelay = 2.0,
  onStart,
  onComplete,
}: UseSingleFeedIngestionOptions): UseSingleFeedIngestionReturn {
  // Check if a workflow for this feed is running via workflow store
  const isIngesting = useWorkflowStore(selectIsFeedIngesting(feedId));
  const addIngestingFeed = useWorkflowStore((state) => state.addIngestingFeed);

  const canIngest = !!(feedId && feedName && feedUrl);

  // Track previous state to detect completion
  const wasIngestingRef = React.useRef(isIngesting);
  React.useEffect(() => {
    // Detect workflow completion: was ingesting, now not
    if (wasIngestingRef.current && !isIngesting) {
      onComplete?.();
    }
    wasIngestingRef.current = isIngesting;
  }, [isIngesting, onComplete]);

  const handleIngest = React.useCallback(async () => {
    if (!canIngest || !feedId) return;

    // Add to workflow store for immediate loading feedback
    addIngestingFeed(feedId);

    try {
      // Callback before starting
      if (onStart) {
        await onStart();
      }

      // Start the single feed ingestion workflow
      const response = await fetch("/api/workflows/ingest-feed", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          feedId,
          feedName,
          feedUrl,
          autoDistill: true,
          enableContentFetch: true,
          enableThumbnail,
          domainFetchDelay,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to start single feed ingestion workflow");
      }

      // Workflow started - SSE will handle progress updates
      // Cleanup is automatic via handleWorkflowUpdate when workflow completes
    } catch (error) {
      console.error("Failed to ingest feed:", error);
      // Note: Feed stays in ingestingFeeds but that's OK - will be cleaned up
      // on next successful workflow update
    }
  }, [
    addIngestingFeed,
    canIngest,
    feedId,
    feedName,
    feedUrl,
    enableThumbnail,
    domainFetchDelay,
    onStart,
  ]);

  return {
    isIngesting,
    handleIngest,
    canIngest,
  };
}
