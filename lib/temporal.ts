/**
 * Temporal client utilities for triggering worker workflows.
 *
 * This module provides functions to start and monitor Temporal workflows
 * from the Next.js server. It's used by API routes that trigger feed
 * ingestion, content fetching, and summarization workflows.
 *
 * @module lib/temporal
 */

import { Client, Connection } from "@temporalio/client";
import { OpenTelemetryWorkflowClientInterceptor } from "@temporalio/interceptors-opentelemetry";

import { createLogger } from "@/lib/logger";
import { isTracingEnabled } from "@/lib/tracing";

const log = createLogger("temporal");

/** Singleton Temporal client instance. */
let client: Client | null = null;

/** Temporal server configuration. */
export interface TemporalConfig {
  /** Temporal server address (e.g., "localhost:7233"). */
  host: string;
  /** Temporal namespace to use. */
  namespace: string;
  /** Task queue for workflow execution. */
  taskQueue: string;
}

/**
 * Gets Temporal configuration from environment variables.
 *
 * @returns Configuration object with defaults
 */
export function getTemporalConfig(): TemporalConfig {
  return {
    host: process.env.TEMPORAL_HOST || "localhost:7233",
    namespace: process.env.TEMPORAL_NAMESPACE || "default",
    taskQueue: process.env.TEMPORAL_TASK_QUEUE || "buun-curator",
  };
}

/**
 * Gets or creates a singleton Temporal client connection.
 *
 * @returns Connected Temporal client
 */
export async function getTemporalClient(): Promise<Client> {
  if (client) {
    return client;
  }

  const config = getTemporalConfig();
  const connection = await Connection.connect({
    address: config.host,
  });

  client = new Client({
    connection,
    namespace: config.namespace,
    interceptors: isTracingEnabled()
      ? { workflow: [new OpenTelemetryWorkflowClientInterceptor()] }
      : undefined,
  });

  return client;
}

/** Options for starting the ReprocessEntriesWorkflow. */
export interface StartReprocessEntriesOptions {
  entryIds: string[];
  fetchContent?: boolean;
  summarize?: boolean;
}

/** Handle returned after starting a workflow. */
export interface WorkflowHandle {
  workflowId: string;
  runId: string;
}

/**
 * Starts the ReprocessEntriesWorkflow to fetch content and/or summarize entries.
 *
 * @param options - Entry IDs and processing flags
 * @returns Workflow handle with IDs for status tracking
 */
export async function startReprocessEntriesWorkflow(
  options: StartReprocessEntriesOptions
): Promise<WorkflowHandle> {
  const { entryIds, fetchContent = true, summarize = true } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  // Include entry IDs in workflow ID for tracking
  // For single entry: reprocess-entries-{entryId}-{random}
  // For multiple: reprocess-entries-{count}-{random}
  const entrySuffix =
    entryIds.length === 1
      ? entryIds[0]
      : `batch-${entryIds.length}`;
  const workflowId = `reprocess-entries-${entrySuffix}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("ReprocessEntriesWorkflow", {
    args: [
      {
        entryIds,
        fetchContent,
        summarize,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/**
 * Starts the AllFeedsIngestionWorkflow to crawl all feeds.
 *
 * All config (autoDistill, enableContentFetch, maxConcurrent, enableThumbnail,
 * domainFetchDelay) is read from environment variables at runtime by the workflow.
 *
 * @returns Workflow handle with IDs for status tracking
 */
export async function startAllFeedsIngestionWorkflow(): Promise<WorkflowHandle> {
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `all-feeds-ingestion-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("AllFeedsIngestionWorkflow", {
    args: [{}], // Empty input - config is read from env vars at runtime
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Options for starting the SingleFeedIngestionWorkflow. */
export interface StartSingleFeedIngestionOptions {
  feedId: string;
  feedName: string;
  feedUrl: string;
  etag?: string;
  lastModified?: string;
  fetchLimit?: number;
  extractionRules?: Record<string, unknown>[];
  autoDistill?: boolean;
  enableContentFetch?: boolean;
  targetLanguage?: string;
  enableThumbnail?: boolean;
  domainFetchDelay?: number;
  /** Entry age filtering (undefined = config default, 0 = no limit). */
  maxEntryAgeDays?: number;
}

/**
 * Starts the SingleFeedIngestionWorkflow to crawl a specific feed.
 *
 * @param options - Feed details and processing options
 * @returns Workflow handle with IDs for status tracking
 */
export async function startSingleFeedIngestionWorkflow(
  options: StartSingleFeedIngestionOptions
): Promise<WorkflowHandle> {
  const {
    feedId,
    feedName,
    feedUrl,
    etag = "",
    lastModified = "",
    fetchLimit = 20,
    extractionRules = null,
    autoDistill = true,
    enableContentFetch = true,
    targetLanguage = "",
    enableThumbnail = false,
    domainFetchDelay = 2.0,
    maxEntryAgeDays,
  } = options;

  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `single-feed-${feedId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("SingleFeedIngestionWorkflow", {
    args: [
      {
        feedId,
        feedName,
        feedUrl,
        etag,
        lastModified,
        fetchLimit,
        extractionRules,
        autoDistill,
        enableContentFetch,
        targetLanguage,
        enableThumbnail,
        domainFetchDelay,
        maxEntryAgeDays,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Possible workflow execution statuses. */
export type WorkflowStatus =
  | "RUNNING"
  | "COMPLETED"
  | "FAILED"
  | "CANCELLED"
  | "TERMINATED"
  | "TIMED_OUT"
  | "UNKNOWN";

/** Result of querying workflow status. */
export interface WorkflowStatusResult {
  status: WorkflowStatus;
  result?: unknown;
  error?: string;
}

/** Translation provider type. */
export type TranslationProvider = "deepl" | "microsoft";

/** Options for starting the TranslationWorkflow. */
export interface StartTranslationOptions {
  entryIds?: string[];
  provider?: TranslationProvider;
}

/**
 * Starts the TranslationWorkflow to translate entries.
 *
 * @param options - Entry IDs and provider options
 * @returns Workflow handle with IDs for status tracking
 */
export async function startTranslationWorkflow(
  options: StartTranslationOptions = {}
): Promise<WorkflowHandle> {
  const { entryIds = null, provider = "microsoft" } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `translation-${provider}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("TranslationWorkflow", {
    args: [
      {
        entryIds,
        provider,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Options for starting the ExtractEntryContextWorkflow. */
export interface StartExtractEntryContextOptions {
  entryId: string;
}

/**
 * Starts the ExtractEntryContextWorkflow to extract context from an entry.
 *
 * @param options - Entry ID to extract context from
 * @returns Workflow handle with IDs for status tracking
 */
export async function startExtractEntryContextWorkflow(
  options: StartExtractEntryContextOptions
): Promise<WorkflowHandle> {
  const { entryId } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `extract-context-${entryId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("ExtractEntryContextWorkflow", {
    args: [
      {
        entryId,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Options for starting the FetchEntryLinksWorkflow. */
export interface StartFetchEntryLinksOptions {
  entryId: string;
  urls: string[];
  timeout?: number;
}

/**
 * Starts the FetchEntryLinksWorkflow to fetch content from URLs.
 *
 * @param options - Entry ID and URLs to fetch
 * @returns Workflow handle with IDs for status tracking
 */
export async function startFetchEntryLinksWorkflow(
  options: StartFetchEntryLinksOptions
): Promise<WorkflowHandle> {
  const { entryId, urls, timeout = 60 } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `fetch-entry-links-${entryId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("FetchEntryLinksWorkflow", {
    args: [
      {
        entryId,
        urls,
        timeout,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Options for starting the ContextCollectionWorkflow. */
export interface StartContextCollectionOptions {
  entryIds: string[];
}

/**
 * Starts the ContextCollectionWorkflow to extract context and enrich entries.
 *
 * @param options - Entry IDs to process
 * @returns Workflow handle with IDs for status tracking
 */
export async function startContextCollectionWorkflow(
  options: StartContextCollectionOptions
): Promise<WorkflowHandle> {
  const { entryIds } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `context-collection-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("ContextCollectionWorkflow", {
    args: [
      {
        entryIds,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/** Options for starting the DeleteEnrichmentWorkflow. */
export interface StartDeleteEnrichmentOptions {
  entryId: string;
  enrichmentType: string;
  source: string;
}

/**
 * Starts the DeleteEnrichmentWorkflow to delete an enrichment.
 *
 * @param options - Entry ID, type, and source of enrichment to delete
 * @returns Workflow handle with IDs for status tracking
 */
export async function startDeleteEnrichmentWorkflow(
  options: StartDeleteEnrichmentOptions
): Promise<WorkflowHandle> {
  const { entryId, enrichmentType, source } = options;
  const client = await getTemporalClient();
  const config = getTemporalConfig();

  const workflowId = `delete-enrichment-${entryId}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;

  const handle = await client.workflow.start("DeleteEnrichmentWorkflow", {
    args: [
      {
        entryId,
        enrichmentType,
        source,
      },
    ],
    taskQueue: config.taskQueue,
    workflowId,
  });

  return {
    workflowId: handle.workflowId,
    runId: handle.firstExecutionRunId,
  };
}

/**
 * Gets the current status of a workflow execution.
 *
 * @param workflowId - The workflow ID to query
 * @returns Status result with optional result data or error message
 */
export async function getWorkflowStatus(
  workflowId: string
): Promise<WorkflowStatusResult> {
  const client = await getTemporalClient();
  const handle = client.workflow.getHandle(workflowId);

  try {
    const description = await handle.describe();
    const status = description.status.name;

    if (status === "COMPLETED") {
      try {
        const result = await handle.result();
        return { status: "COMPLETED", result };
      } catch {
        return { status: "COMPLETED" };
      }
    }

    if (status === "RUNNING") {
      return { status: "RUNNING" };
    }

    if (status === "FAILED") {
      return { status: "FAILED", error: "Workflow failed" };
    }

    if (status === "CANCELLED") {
      return { status: "CANCELLED" };
    }

    if (status === "TERMINATED") {
      return { status: "TERMINATED" };
    }

    if (status === "TIMED_OUT") {
      return { status: "TIMED_OUT" };
    }

    return { status: "UNKNOWN" };
  } catch (error) {
    return {
      status: "UNKNOWN",
      error: error instanceof Error ? error.message : "Unknown error",
    };
  }
}

// ============================================================================
// Workflow Progress Query Types
// ============================================================================

/** Entry progress state from Python workflow. */
export interface EntryProgressState {
  entryId: string;
  title: string;
  status: "pending" | "fetching" | "fetched" | "distilling" | "completed" | "error";
  changedAt: string;
  error?: string;
}

/** Workflow progress status. */
export type WorkflowProgressStatus = "running" | "completed" | "error";

/** Base workflow progress from Temporal Query. */
export interface WorkflowProgress {
  workflowId: string;
  workflowType: string;
  status: WorkflowProgressStatus;
  currentStep: string;
  message: string;
  startedAt: string;
  updatedAt: string;
  error?: string;
  /** Parent workflow ID (for child workflows). */
  parentWorkflowId?: string;
  /** Whether to show toast notification (default: true). */
  showToast?: boolean;
}

/**
 * Workflow progress with hierarchical children.
 *
 * Used by workflow-store to maintain parent-child relationships.
 */
export interface WorkflowProgressNode extends WorkflowProgress {
  /** Child workflows keyed by workflow ID. */
  children: Record<string, WorkflowProgressNode>;
}

/** ReprocessEntriesWorkflow progress. */
export interface ReprocessEntriesProgress extends WorkflowProgress {
  workflowType: "ReprocessEntries";
  entryProgress: Record<string, EntryProgressState>;
  totalEntries: number;
  entriesFetched: number;
  entriesDistilled: number;
}

/** SingleFeedIngestionWorkflow progress. */
export interface SingleFeedIngestionProgress extends WorkflowProgress {
  workflowType: "SingleFeedIngestion";
  feedId: string;
  feedName: string;
  parentWorkflowId: string;
  totalEntries: number;
  entriesCreated: number;
  entriesSkipped: number;
  contentsFetched: number;
  entriesDistilled: number;
}

/** ScheduleFetchWorkflow progress. */
export interface ScheduleFetchProgress extends WorkflowProgress {
  workflowType: "ScheduleFetch";
  parentWorkflowId: string;
  totalEntries: number;
  totalDomains: number;
  domainsCompleted: number;
  entriesFetched: number;
  entriesDistilled: number;
  skippedCount: number;
}

/** DomainFetchWorkflow progress. */
export interface DomainFetchProgress extends WorkflowProgress {
  workflowType: "DomainFetch";
  domain: string;
  parentWorkflowId: string;
  currentEntryIndex: number;
  currentEntryTitle: string;
  entryProgress: Record<string, EntryProgressState>;
  totalEntries: number;
  entriesFetched: number;
  entriesDistilled: number;
  entriesFailed: number;
}

/** AllFeedsIngestionWorkflow progress. */
export interface AllFeedsIngestionProgress extends WorkflowProgress {
  workflowType: "AllFeedsIngestion";
  feedsTotal: number;
  feedsCompleted: number;
  feedsProcessed: number;
  feedsSkipped: number;
  feedsFailed: number;
  currentBatch: number;
  totalBatches: number;
  entriesCreated: number;
  contentsFetched: number;
  entriesDistilled: number;
}

/** TranslationWorkflow progress. */
export interface TranslationProgress extends WorkflowProgress {
  workflowType: "Translation";
  provider: string;
  entryProgress: Record<string, EntryProgressState>;
  totalEntries: number;
  entriesTranslated: number;
}

/** ContentDistillationWorkflow progress. */
export interface ContentDistillationProgress extends WorkflowProgress {
  workflowType: "ContentDistillation";
  entryProgress: Record<string, EntryProgressState>;
  totalEntries: number;
  entriesDistilled: number;
}

/** ContextCollectionWorkflow progress. */
export interface ContextCollectionProgress extends WorkflowProgress {
  workflowType: "ContextCollection";
  entryProgress: Record<string, EntryProgressState>;
  totalEntries: number;
  successfulExtractions: number;
  failedExtractions: number;
  enrichmentCandidatesCount: number;
}

/** URL progress state for FetchEntryLinksWorkflow. */
export interface UrlProgressState {
  url: string;
  status: "pending" | "fetching" | "completed" | "error";
  title: string;
  changedAt: string;
  error?: string;
}

/** FetchEntryLinksWorkflow progress. */
export interface FetchEntryLinksProgress extends WorkflowProgress {
  workflowType: "FetchEntryLinks";
  entryId: string;
  urlProgress: Record<string, UrlProgressState>;
  totalUrls: number;
  processedUrls: number;
}

/** DeleteEnrichmentWorkflow progress. */
export interface DeleteEnrichmentProgress extends WorkflowProgress {
  workflowType: "DeleteEnrichment";
  entryId: string;
  enrichmentType: string;
  source: string;
}

/** Active workflow info from listWorkflows. */
export interface ActiveWorkflowInfo {
  workflowId: string;
  workflowType: string;
  startTime: Date;
  progress: WorkflowProgress | null;
}

/**
 * Query workflow progress using Temporal Query.
 *
 * @param workflowId - The workflow ID to query
 * @returns Workflow progress or null if query fails
 */
export async function queryWorkflowProgress(
  workflowId: string
): Promise<WorkflowProgress | null> {
  const client = await getTemporalClient();
  const handle = client.workflow.getHandle(workflowId);

  try {
    const progress = await handle.query<WorkflowProgress>("get_progress");
    return progress;
  } catch (error) {
    log.error({ workflowId, error }, "failed to query progress");
    return null;
  }
}

/**
 * List all running workflows and their progress.
 *
 * @returns Array of active workflow info with progress
 */
export async function listActiveWorkflows(): Promise<ActiveWorkflowInfo[]> {
  const client = await getTemporalClient();
  const results: ActiveWorkflowInfo[] = [];

  try {
    const workflows = client.workflow.list({
      query: 'ExecutionStatus="Running"',
    });

    for await (const workflow of workflows) {
      let progress: WorkflowProgress | null = null;
      try {
        const handle = client.workflow.getHandle(workflow.workflowId);
        progress = await handle.query<WorkflowProgress>("get_progress");
      } catch {
        // Query might fail for workflows without get_progress handler
      }

      results.push({
        workflowId: workflow.workflowId,
        workflowType: String(workflow.type || "Unknown"),
        startTime: workflow.startTime,
        progress,
      });
    }
  } catch (error) {
    log.error({ error }, "failed to list workflows");
  }

  return results;
}
