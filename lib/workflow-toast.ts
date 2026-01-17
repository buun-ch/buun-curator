/**
 * Toast message generation for workflow progress.
 *
 * Generates appropriate toast messages based on workflow type and status.
 * Currently supports ReprocessEntriesWorkflow; other workflows can be added.
 *
 * @module lib/workflow-toast
 */

import type {
  WorkflowProgressNode,
  ReprocessEntriesProgress,
  SingleFeedIngestionProgress,
  AllFeedsIngestionProgress,
  DomainFetchProgress,
  TranslationProgress,
  ContentDistillationProgress,
  ContextCollectionProgress,
  EntryProgressState,
} from "@/lib/temporal";

/** Toast message type for sonner. */
export type ToastType = "loading" | "success" | "error";

/** Toast message to display. */
export interface WorkflowToastMessage {
  /** Main toast title. */
  title: string;
  /** Optional description text. */
  description?: string;
  /** Toast type (loading, success, error). */
  type: ToastType;
}

/**
 * Truncate a string to a maximum length.
 *
 * @param text - Text to truncate
 * @param maxLength - Maximum length
 * @returns Truncated text with ellipsis if needed
 */
function truncate(text: string, maxLength: number = 30): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Type guard for ReprocessEntriesProgress.
 */
function isReprocessEntriesProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & ReprocessEntriesProgress {
  return workflow.workflowType === "ReprocessEntries";
}

/**
 * Type guard for SingleFeedIngestionProgress.
 */
function isSingleFeedIngestionProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & SingleFeedIngestionProgress {
  return workflow.workflowType === "SingleFeedIngestion";
}

/**
 * Type guard for AllFeedsIngestionProgress.
 */
function isAllFeedsIngestionProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & AllFeedsIngestionProgress {
  return workflow.workflowType === "AllFeedsIngestion";
}

/**
 * Type guard for DomainFetchProgress.
 */
function isDomainFetchProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & DomainFetchProgress {
  return workflow.workflowType === "DomainFetch";
}

/**
 * Type guard for TranslationProgress.
 */
function isTranslationProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & TranslationProgress {
  return workflow.workflowType === "Translation";
}

/**
 * Type guard for ContentDistillationProgress.
 */
function isContentDistillationProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & ContentDistillationProgress {
  return workflow.workflowType === "ContentDistillation";
}

/**
 * Type guard for ContextCollectionProgress.
 */
function isContextCollectionProgress(
  workflow: WorkflowProgressNode
): workflow is WorkflowProgressNode & ContextCollectionProgress {
  return workflow.workflowType === "ContextCollection";
}

/** Aggregated entry status counts. */
interface EntryStatusCounts {
  total: number;
  pending: number;
  fetching: number;
  fetched: number;
  distilling: number;
  completed: number;
  error: number;
}

/**
 * Collect all entry_progress from DomainFetchWorkflow children in the tree.
 *
 * Traverses: SingleFeedIngestion -> ScheduleFetch -> DomainFetch(s)
 */
function collectEntryProgress(
  workflow: WorkflowProgressNode
): Record<string, EntryProgressState> {
  const result: Record<string, EntryProgressState> = {};

  // If this is a DomainFetchWorkflow, collect its entry_progress
  if (isDomainFetchProgress(workflow) && workflow.entryProgress) {
    Object.assign(result, workflow.entryProgress);
  }

  // Recursively collect from children
  for (const child of Object.values(workflow.children)) {
    Object.assign(result, collectEntryProgress(child));
  }

  return result;
}

/**
 * Count entries by status from entry_progress.
 */
function countEntryStatuses(
  entryProgress: Record<string, EntryProgressState>
): EntryStatusCounts {
  const counts: EntryStatusCounts = {
    total: 0,
    pending: 0,
    fetching: 0,
    fetched: 0,
    distilling: 0,
    completed: 0,
    error: 0,
  };

  for (const entry of Object.values(entryProgress)) {
    counts.total++;
    switch (entry.status) {
      case "pending":
        counts.pending++;
        break;
      case "fetching":
        counts.fetching++;
        break;
      case "fetched":
        counts.fetched++;
        break;
      case "distilling":
        counts.distilling++;
        break;
      case "completed":
        counts.completed++;
        break;
      case "error":
        counts.error++;
        break;
    }
  }

  return counts;
}

/**
 * Get the first entry title from ReprocessEntriesProgress.
 */
function getFirstEntryTitle(
  entryProgress: Record<string, EntryProgressState>
): string | undefined {
  const entries = Object.values(entryProgress);
  if (entries.length === 1 && entries[0].title) {
    return entries[0].title;
  }
  return undefined;
}

/**
 * Generate toast message for ReprocessEntriesWorkflow.
 */
function getReprocessEntriesToast(
  workflow: WorkflowProgressNode & ReprocessEntriesProgress
): WorkflowToastMessage {
  const { status, entryProgress, totalEntries, entriesFetched, error } = workflow;

  // Get entry title for single-entry workflows
  const entryTitle = getFirstEntryTitle(entryProgress);

  if (status === "running") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Fetching: ${truncate(entryTitle)}`,
        description: "This may take a moment",
        type: "loading",
      };
    }
    return {
      title: `Fetching ${entriesFetched}/${totalEntries} entries`,
      type: "loading",
    };
  }

  if (status === "completed") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Updated: ${truncate(entryTitle)}`,
        type: "success",
      };
    }
    return {
      title: `Updated ${totalEntries} entries`,
      type: "success",
    };
  }

  // Error status
  return {
    title: entryTitle ? `Failed: ${truncate(entryTitle)}` : "Fetch failed",
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for SingleFeedIngestionWorkflow.
 *
 * Collects entry_progress from child DomainFetchWorkflows to show accurate
 * fetch/distill progress.
 */
function getSingleFeedIngestionToast(
  workflow: WorkflowProgressNode & SingleFeedIngestionProgress
): WorkflowToastMessage {
  const { status, feedName, entriesCreated, error } = workflow;

  const name = truncate(feedName || "Unknown Feed", 25);

  if (status === "running") {
    // Collect entry progress from DomainFetchWorkflow children
    const entryProgress = collectEntryProgress(workflow);
    const counts = countEntryStatuses(entryProgress);

    if (counts.total > 0) {
      // fetched = entries past the fetching stage
      const fetched = counts.fetched + counts.distilling + counts.completed;
      return {
        title: `Fetching: ${name}`,
        description: `fetch ${fetched}/${counts.total}`,
        type: "loading",
      };
    }

    // Before DomainFetch children exist (crawling phase)
    return {
      title: `Crawling: ${name}`,
      description:
        entriesCreated > 0 ? `${entriesCreated} new entries` : undefined,
      type: "loading",
    };
  }

  if (status === "completed") {
    // Collect final entry progress for summary
    const entryProgress = collectEntryProgress(workflow);
    const counts = countEntryStatuses(entryProgress);

    // Build summary description
    const parts: string[] = [];
    if (entriesCreated > 0) parts.push(`${entriesCreated} new`);
    if (counts.total > 0) {
      const fetched = counts.fetched + counts.distilling + counts.completed;
      if (fetched > 0) parts.push(`${fetched} fetched`);
      if (counts.completed > 0) parts.push(`${counts.completed} distilled`);
    }

    return {
      title: `Ingested: ${name}`,
      description: parts.length > 0 ? parts.join(", ") : "No new entries",
      type: "success",
    };
  }

  // Error status
  return {
    title: `Failed: ${name}`,
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for AllFeedsIngestionWorkflow.
 */
function getAllFeedsIngestionToast(
  workflow: WorkflowProgressNode & AllFeedsIngestionProgress
): WorkflowToastMessage {
  const {
    status,
    feedsTotal,
    feedsCompleted,
    currentBatch,
    totalBatches,
    entriesCreated,
    entriesDistilled,
    error,
  } = workflow;

  if (status === "running") {
    if (feedsTotal === 0) {
      return {
        title: "Ingesting feeds...",
        description: "Listing feeds...",
        type: "loading",
      };
    }

    // Show batch and feed progress
    const batchInfo =
      totalBatches > 1 ? `Batch ${currentBatch}/${totalBatches}, ` : "";
    return {
      title: "Ingesting feeds...",
      description: `${batchInfo}${feedsCompleted}/${feedsTotal} feeds`,
      type: "loading",
    };
  }

  if (status === "completed") {
    // Build summary
    const parts: string[] = [];
    parts.push(`${feedsCompleted} feeds`);
    if (entriesCreated > 0) parts.push(`${entriesCreated} new`);
    if (entriesDistilled > 0) parts.push(`${entriesDistilled} distilled`);

    return {
      title: "Feed ingestion complete",
      description: parts.join(", "),
      type: "success",
    };
  }

  // Error status
  return {
    title: "Feed ingestion failed",
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for TranslationWorkflow.
 */
function getTranslationToast(
  workflow: WorkflowProgressNode & TranslationProgress
): WorkflowToastMessage {
  const { status, provider, entryProgress, totalEntries, entriesTranslated, error } =
    workflow;

  // Get provider name for display
  const providerLabel = provider === "deepl" ? "DeepL" : "Microsoft";

  // Get entry title for single-entry workflows
  const entryTitle = getFirstEntryTitle(entryProgress);

  if (status === "running") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Translating: ${truncate(entryTitle)}`,
        description: `Using ${providerLabel}`,
        type: "loading",
      };
    }
    return {
      title: `Translating ${totalEntries} entries`,
      description: `Using ${providerLabel}`,
      type: "loading",
    };
  }

  if (status === "completed") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Translated: ${truncate(entryTitle)}`,
        type: "success",
      };
    }
    return {
      title: `Translated ${entriesTranslated} entries`,
      type: "success",
    };
  }

  // Error status
  return {
    title: entryTitle ? `Translation failed: ${truncate(entryTitle)}` : "Translation failed",
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for ContentDistillationWorkflow.
 */
function getContentDistillationToast(
  workflow: WorkflowProgressNode & ContentDistillationProgress
): WorkflowToastMessage {
  const { status, entryProgress, totalEntries, entriesDistilled, error } = workflow;

  // Get entry title for single-entry workflows
  const entryTitle = getFirstEntryTitle(entryProgress);

  if (status === "running") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Distilling: ${truncate(entryTitle)}`,
        description: "Extracting summary...",
        type: "loading",
      };
    }
    return {
      title: `Distilling ${entriesDistilled}/${totalEntries} entries`,
      type: "loading",
    };
  }

  if (status === "completed") {
    if (entryTitle && totalEntries === 1) {
      return {
        title: `Distilled: ${truncate(entryTitle)}`,
        type: "success",
      };
    }
    return {
      title: `Distilled ${entriesDistilled} entries`,
      type: "success",
    };
  }

  // Error status
  return {
    title: entryTitle ? `Distillation failed: ${truncate(entryTitle)}` : "Distillation failed",
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for ContextCollectionWorkflow.
 */
function getContextCollectionToast(
  workflow: WorkflowProgressNode & ContextCollectionProgress
): WorkflowToastMessage {
  const {
    status,
    totalEntries,
    successfulExtractions,
    failedExtractions,
    enrichmentCandidatesCount,
    currentStep,
    error,
  } = workflow;

  if (status === "running") {
    // Show different messages based on current step
    if (currentStep === "extract") {
      return {
        title: "Extracting contexts...",
        description: `${successfulExtractions}/${totalEntries} entries`,
        type: "loading",
      };
    }
    if (currentStep === "analyze") {
      return {
        title: "Analyzing contexts...",
        type: "loading",
      };
    }
    if (currentStep === "enrich") {
      return {
        title: "Enriching entities...",
        description: `${enrichmentCandidatesCount} candidates`,
        type: "loading",
      };
    }
    if (currentStep === "save") {
      return {
        title: "Saving enrichments...",
        type: "loading",
      };
    }
    return {
      title: "Collecting contexts...",
      type: "loading",
    };
  }

  if (status === "completed") {
    const parts: string[] = [];
    if (successfulExtractions > 0) parts.push(`${successfulExtractions} extracted`);
    if (enrichmentCandidatesCount > 0) parts.push(`${enrichmentCandidatesCount} enriched`);

    return {
      title: "Context collection complete",
      description: parts.length > 0 ? parts.join(", ") : undefined,
      type: "success",
    };
  }

  // Error or partial status
  if (failedExtractions > 0 && successfulExtractions > 0) {
    return {
      title: "Context collection partial",
      description: `${successfulExtractions} succeeded, ${failedExtractions} failed`,
      type: "error",
    };
  }

  return {
    title: "Context collection failed",
    description: error || undefined,
    type: "error",
  };
}

/**
 * Generate toast message for a generic workflow (fallback).
 */
function getGenericWorkflowToast(
  workflow: WorkflowProgressNode
): WorkflowToastMessage {
  const { status, workflowType, message, error } = workflow;

  const label = getWorkflowLabel(workflowType);

  if (status === "running") {
    return {
      title: message || `Running: ${label}`,
      type: "loading",
    };
  }

  if (status === "completed") {
    return {
      title: `Completed: ${label}`,
      type: "success",
    };
  }

  return {
    title: `Failed: ${label}`,
    description: error || undefined,
    type: "error",
  };
}

/**
 * Get human-readable workflow label.
 */
function getWorkflowLabel(workflowType: string): string {
  switch (workflowType) {
    case "ReprocessEntries":
      return "Reprocess Entries";
    case "SingleFeedIngestion":
      return "Feed Ingestion";
    case "AllFeedsIngestion":
      return "All Feeds Ingestion";
    case "ContentDistillation":
      return "Content Distillation";
    case "DeepLTranslation":
    case "MSTranslation":
      return "Translation";
    case "ContextCollection":
      return "Context Collection";
    default:
      return workflowType;
  }
}

/**
 * Generate toast message from a top-level workflow.
 *
 * Returns appropriate toast message based on workflow type and current status.
 * Extend this function to add support for more workflow types.
 *
 * @param workflow - Top-level workflow progress node
 * @returns Toast message to display
 */
export function getWorkflowToastMessage(
  workflow: WorkflowProgressNode
): WorkflowToastMessage {
  // Handle ReprocessEntriesWorkflow with type-specific logic
  if (isReprocessEntriesProgress(workflow)) {
    return getReprocessEntriesToast(workflow);
  }

  // Handle SingleFeedIngestionWorkflow
  if (isSingleFeedIngestionProgress(workflow)) {
    return getSingleFeedIngestionToast(workflow);
  }

  // Handle AllFeedsIngestionWorkflow
  if (isAllFeedsIngestionProgress(workflow)) {
    return getAllFeedsIngestionToast(workflow);
  }

  // Handle TranslationWorkflows (DeepL and MS)
  if (isTranslationProgress(workflow)) {
    return getTranslationToast(workflow);
  }

  // Handle ContentDistillationWorkflow
  if (isContentDistillationProgress(workflow)) {
    return getContentDistillationToast(workflow);
  }

  // Handle ContextCollectionWorkflow
  if (isContextCollectionProgress(workflow)) {
    return getContextCollectionToast(workflow);
  }

  // Fallback to generic toast
  return getGenericWorkflowToast(workflow);
}
