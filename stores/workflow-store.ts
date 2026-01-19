/**
 * Zustand store for workflow progress state.
 *
 * Manages active workflow notifications from SSE events.
 * Maintains hierarchical parent-child relationships.
 * Not persisted - ephemeral state only.
 *
 * @module stores/workflow-store
 */

import { create } from "zustand";
import type {
  EntryProgressState,
  WorkflowProgress,
  WorkflowProgressNode as BaseWorkflowProgressNode,
} from "@/lib/temporal";

/**
 * Extended WorkflowProgressNode with client-side timestamp.
 * Used for stale workflow detection and cleanup.
 */
interface WorkflowProgressNode extends BaseWorkflowProgressNode {
  /** Client-side timestamp of last progress update (Date.now()). */
  lastSeenAt: number;
  /** Override children to use extended type. */
  children: Record<string, WorkflowProgressNode>;
}

/** Delay before hiding the status bar after all workflows complete (ms). */
const STATUS_BAR_AUTO_HIDE_DELAY = 1000;

/** Timer ID for status bar auto-hide. */
let hideTimerId: ReturnType<typeof setTimeout> | null = null;

/** Timer ID for stale workflow cleanup. */
let cleanupTimerId: ReturnType<typeof setInterval> | null = null;

/** Interval for checking stale workflows (ms). */
const STALE_CHECK_INTERVAL_MS = 30_000; // 30 seconds

/** Threshold for considering a workflow stale (ms). */
const STALE_WORKFLOW_THRESHOLD_MS = 3 * 60 * 1000; // 3 minutes

/** Default panel height in pixels. */
const DEFAULT_PANEL_HEIGHT = 300;

/** Minimum panel height in pixels. */
const MIN_PANEL_HEIGHT = 100;

/** Maximum panel height in pixels. */
const MAX_PANEL_HEIGHT = 600;

interface WorkflowStoreState {
  /**
   * Top-level workflows keyed by workflow ID.
   * Only workflows without parentWorkflowId are stored here.
   * Child workflows are nested in their parent's children field.
   */
  workflows: Record<string, WorkflowProgressNode>;

  /**
   * Orphan workflows waiting for their parent.
   * When a child workflow arrives before its parent, it's stored here.
   * Once the parent arrives, orphans are moved to the parent's children.
   */
  orphanWorkflows: Record<string, WorkflowProgressNode>;

  /**
   * Entry IDs currently being refreshed.
   * Populated immediately when refresh starts (before SSE kicks in).
   * Cleared when workflow completes or errors.
   */
  refreshingEntries: Set<string>;

  /**
   * Feed IDs currently being ingested.
   * Populated immediately when ingestion starts (before SSE kicks in).
   * Cleared when workflow completes or errors.
   */
  ingestingFeeds: Set<string>;

  /**
   * Entry IDs currently being translated.
   * Populated immediately when translation starts (before SSE kicks in).
   * Cleared when workflow completes or errors.
   */
  translatingEntries: Set<string>;

  /**
   * Entry IDs that have been distilled (summary generated).
   * Used to trigger UI updates when distillation completes.
   * Cleared when the entry is consumed (e.g., refetched in content viewer).
   */
  distilledEntryIds: Set<string>;

  /** Whether the status panel is expanded. */
  panelOpen: boolean;
  /** Whether the status bar should be visible. */
  statusBarVisible: boolean;
  /** SSE connection status. */
  connectionStatus: "connected" | "disconnected" | "connecting";
  /** Panel height in pixels. */
  panelHeight: number;

  // Actions
  /** Handle workflow update from Temporal Query. */
  handleWorkflowUpdate: (progress: WorkflowProgress) => void;
  /** Remove a workflow from tracking. */
  removeWorkflow: (workflowId: string) => void;
  /** Clear all completed/errored workflows. */
  clearFinished: () => void;
  /** Toggle panel open/closed. */
  togglePanel: () => void;
  /** Set panel open state. */
  setPanelOpen: (open: boolean) => void;
  /** Set connection status. */
  setConnectionStatus: (
    status: "connected" | "disconnected" | "connecting",
  ) => void;
  /** Set panel height (clamped to min/max). */
  setPanelHeight: (height: number) => void;
  /** Add an entry ID to refreshing set (for immediate loading feedback). */
  addRefreshingEntry: (entryId: string) => void;
  /** Add a feed ID to ingesting set (for immediate loading feedback). */
  addIngestingFeed: (feedId: string) => void;
  /** Add an entry ID to translating set (for immediate loading feedback). */
  addTranslatingEntry: (entryId: string) => void;
  /** Add entry IDs to distilled set (for triggering UI updates). */
  addDistilledEntryIds: (entryIds: string[]) => void;
  /** Clear an entry ID from distilled set (after consuming the update). */
  clearDistilledEntryId: (entryId: string) => void;
  /** Remove workflows that haven't been updated within the threshold. */
  cleanupStaleWorkflows: () => void;
  /** Start periodic stale workflow cleanup. */
  startCleanupInterval: () => void;
  /** Stop periodic stale workflow cleanup. */
  stopCleanupInterval: () => void;
}

/** Helper to clear the auto-hide timer. */
function clearHideTimer() {
  if (hideTimerId) {
    clearTimeout(hideTimerId);
    hideTimerId = null;
  }
}

/** Convert WorkflowProgress to WorkflowProgressNode with empty children. */
function toNode(progress: WorkflowProgress): WorkflowProgressNode {
  return { ...progress, children: {}, lastSeenAt: Date.now() };
}

/**
 * Check if any workflows are running (recursively including children).
 */
function hasRunningWorkflows(
  workflows: Record<string, WorkflowProgressNode>,
): boolean {
  for (const wf of Object.values(workflows)) {
    if (wf.status === "running") return true;
    if (hasRunningWorkflows(wf.children)) return true;
  }
  return false;
}

/**
 * Find a workflow by ID in the tree (including children).
 * Returns the parent record and the workflow if found.
 */
function findWorkflowInTree(
  workflows: Record<string, WorkflowProgressNode>,
  workflowId: string,
): {
  parent: Record<string, WorkflowProgressNode>;
  node: WorkflowProgressNode;
} | null {
  if (workflows[workflowId]) {
    return { parent: workflows, node: workflows[workflowId] };
  }
  for (const wf of Object.values(workflows)) {
    const found = findWorkflowInTree(wf.children, workflowId);
    if (found) return found;
  }
  return null;
}

/**
 * Update a workflow node in place with new progress data.
 * Preserves the children structure and updates lastSeenAt.
 */
function updateNode(
  existing: WorkflowProgressNode,
  progress: WorkflowProgress,
): WorkflowProgressNode {
  return {
    ...progress,
    children: existing.children,
    lastSeenAt: Date.now(),
  };
}

/**
 * Collect orphans that belong to a parent workflow.
 */
function collectOrphansForParent(
  orphans: Record<string, WorkflowProgressNode>,
  parentId: string,
): {
  collected: Record<string, WorkflowProgressNode>;
  remaining: Record<string, WorkflowProgressNode>;
} {
  const collected: Record<string, WorkflowProgressNode> = {};
  const remaining: Record<string, WorkflowProgressNode> = {};

  for (const [id, orphan] of Object.entries(orphans)) {
    if (orphan.parentWorkflowId === parentId) {
      collected[id] = orphan;
    } else {
      remaining[id] = orphan;
    }
  }

  return { collected, remaining };
}

/**
 * Filter workflows to only keep running ones (recursively).
 */
function filterRunningWorkflows(
  workflows: Record<string, WorkflowProgressNode>,
): Record<string, WorkflowProgressNode> {
  const result: Record<string, WorkflowProgressNode> = {};

  for (const [id, wf] of Object.entries(workflows)) {
    const filteredChildren = filterRunningWorkflows(wf.children);
    // Keep if running OR has running children
    if (wf.status === "running" || Object.keys(filteredChildren).length > 0) {
      result[id] = { ...wf, children: filteredChildren };
    }
  }

  return result;
}

/**
 * Remove a workflow by ID from the tree.
 * Returns new tree without the workflow.
 */
function removeFromTree(
  workflows: Record<string, WorkflowProgressNode>,
  workflowId: string,
): Record<string, WorkflowProgressNode> {
  const result: Record<string, WorkflowProgressNode> = {};

  for (const [id, wf] of Object.entries(workflows)) {
    if (id === workflowId) continue; // Skip this one
    result[id] = {
      ...wf,
      children: removeFromTree(wf.children, workflowId),
    };
  }

  return result;
}

/**
 * Filter out stale top-level workflows that haven't been updated within the threshold.
 * Only checks top-level workflows (those without parentWorkflowId).
 * Children are removed together with their parent.
 */
function filterStaleTopLevelWorkflows(
  workflows: Record<string, WorkflowProgressNode>,
  thresholdMs: number = STALE_WORKFLOW_THRESHOLD_MS,
): Record<string, WorkflowProgressNode> {
  const now = Date.now();
  const result: Record<string, WorkflowProgressNode> = {};

  for (const [id, wf] of Object.entries(workflows)) {
    const isStale = now - wf.lastSeenAt > thresholdMs;

    // Only remove if stale (children are kept as-is or removed with parent)
    if (!isStale) {
      result[id] = wf;
    }
  }

  return result;
}

export const useWorkflowStore = create<WorkflowStoreState>()((set, get) => ({
  workflows: {},
  orphanWorkflows: {},
  refreshingEntries: new Set<string>(),
  ingestingFeeds: new Set<string>(),
  translatingEntries: new Set<string>(),
  distilledEntryIds: new Set<string>(),
  panelOpen: false,
  statusBarVisible: false,
  connectionStatus: "disconnected",
  panelHeight: DEFAULT_PANEL_HEIGHT,

  handleWorkflowUpdate: (progress) =>
    set((state) => {
      const { parentWorkflowId, workflowId } = progress;

      // Cancel any pending hide timer and show the status bar
      clearHideTimer();

      let newWorkflows = { ...state.workflows };
      let newOrphans = { ...state.orphanWorkflows };

      if (!parentWorkflowId) {
        // Top-level workflow
        const existing = newWorkflows[workflowId];
        if (existing) {
          // Update existing top-level workflow
          newWorkflows[workflowId] = updateNode(existing, progress);
        } else {
          // New top-level workflow
          const node = toNode(progress);
          // Check for orphans that belong to this workflow
          const { collected, remaining } = collectOrphansForParent(
            newOrphans,
            workflowId,
          );
          node.children = collected;
          newOrphans = remaining;
          newWorkflows[workflowId] = node;
        }
      } else {
        // Child workflow - find parent
        const parentFound = findWorkflowInTree(newWorkflows, parentWorkflowId);

        if (parentFound) {
          // Parent exists - add/update in parent's children
          const { node: parentNode } = parentFound;
          const existingChild = parentNode.children[workflowId];
          if (existingChild) {
            parentNode.children[workflowId] = updateNode(
              existingChild,
              progress,
            );
          } else {
            parentNode.children[workflowId] = toNode(progress);
          }
        } else {
          // Parent not yet arrived - store as orphan
          const existingOrphan = newOrphans[workflowId];
          if (existingOrphan) {
            newOrphans[workflowId] = updateNode(existingOrphan, progress);
          } else {
            newOrphans[workflowId] = toNode(progress);
          }
        }
      }

      // Schedule auto-hide if no workflows are running
      if (
        !hasRunningWorkflows(newWorkflows) &&
        Object.keys(newOrphans).length === 0
      ) {
        clearHideTimer();
        hideTimerId = setTimeout(() => {
          set({ statusBarVisible: false });
        }, STATUS_BAR_AUTO_HIDE_DELAY);
      }

      // Clean up refreshingEntries based on entryProgress
      let newRefreshingEntries = state.refreshingEntries;
      const entryProgress = (
        progress as { entryProgress?: Record<string, EntryProgressState> }
      ).entryProgress;
      if (entryProgress) {
        for (const entry of Object.values(entryProgress)) {
          if (
            entry.entryId &&
            (entry.status === "completed" || entry.status === "error") &&
            state.refreshingEntries.has(entry.entryId)
          ) {
            // Lazily create new Set only when needed
            if (newRefreshingEntries === state.refreshingEntries) {
              newRefreshingEntries = new Set(state.refreshingEntries);
            }
            newRefreshingEntries.delete(entry.entryId);
          }
        }
      }

      // Clean up ingestingFeeds when SingleFeedIngestion workflow completes
      let newIngestingFeeds = state.ingestingFeeds;
      if (
        progress.workflowType === "SingleFeedIngestion" &&
        (progress.status === "completed" || progress.status === "error")
      ) {
        const feedId = (progress as { feedId?: string }).feedId;
        if (feedId && state.ingestingFeeds.has(feedId)) {
          newIngestingFeeds = new Set(state.ingestingFeeds);
          newIngestingFeeds.delete(feedId);
        }
      }

      // Clean up translatingEntries when Translation workflow completes
      let newTranslatingEntries = state.translatingEntries;
      if (
        progress.workflowType === "Translation" &&
        (progress.status === "completed" || progress.status === "error")
      ) {
        const translationEntryProgress = (
          progress as { entryProgress?: Record<string, EntryProgressState> }
        ).entryProgress;
        if (translationEntryProgress) {
          for (const entry of Object.values(translationEntryProgress)) {
            if (entry.entryId && state.translatingEntries.has(entry.entryId)) {
              if (newTranslatingEntries === state.translatingEntries) {
                newTranslatingEntries = new Set(state.translatingEntries);
              }
              newTranslatingEntries.delete(entry.entryId);
            }
          }
        }
      }

      return {
        statusBarVisible: true,
        workflows: newWorkflows,
        orphanWorkflows: newOrphans,
        refreshingEntries: newRefreshingEntries,
        ingestingFeeds: newIngestingFeeds,
        translatingEntries: newTranslatingEntries,
      };
    }),

  removeWorkflow: (workflowId) =>
    set((state) => {
      let newWorkflows = removeFromTree(state.workflows, workflowId);
      const { [workflowId]: _, ...newOrphans } = state.orphanWorkflows;

      // Hide if no workflows remain
      if (
        Object.keys(newWorkflows).length === 0 &&
        Object.keys(newOrphans).length === 0
      ) {
        clearHideTimer();
        return {
          workflows: newWorkflows,
          orphanWorkflows: newOrphans,
          statusBarVisible: false,
        };
      }
      return { workflows: newWorkflows, orphanWorkflows: newOrphans };
    }),

  clearFinished: () =>
    set((state) => {
      const running = filterRunningWorkflows(state.workflows);
      const runningOrphans = Object.fromEntries(
        Object.entries(state.orphanWorkflows).filter(
          ([, wf]) => wf.status === "running",
        ),
      );

      // Hide if no workflows remain
      if (
        Object.keys(running).length === 0 &&
        Object.keys(runningOrphans).length === 0
      ) {
        clearHideTimer();
        return {
          workflows: running,
          orphanWorkflows: runningOrphans,
          statusBarVisible: false,
        };
      }
      return { workflows: running, orphanWorkflows: runningOrphans };
    }),

  togglePanel: () => set((state) => ({ panelOpen: !state.panelOpen })),

  setPanelOpen: (open) => set({ panelOpen: open }),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setPanelHeight: (height) =>
    set({
      panelHeight: Math.max(
        MIN_PANEL_HEIGHT,
        Math.min(MAX_PANEL_HEIGHT, height),
      ),
    }),

  addRefreshingEntry: (entryId) =>
    set((state) => ({
      refreshingEntries: new Set(state.refreshingEntries).add(entryId),
    })),

  addIngestingFeed: (feedId) =>
    set((state) => ({
      ingestingFeeds: new Set(state.ingestingFeeds).add(feedId),
    })),

  addTranslatingEntry: (entryId) =>
    set((state) => ({
      translatingEntries: new Set(state.translatingEntries).add(entryId),
    })),

  addDistilledEntryIds: (entryIds) =>
    set((state) => {
      const newSet = new Set(state.distilledEntryIds);
      for (const id of entryIds) {
        newSet.add(id);
      }
      return { distilledEntryIds: newSet };
    }),

  clearDistilledEntryId: (entryId) =>
    set((state) => {
      const newSet = new Set(state.distilledEntryIds);
      newSet.delete(entryId);
      return { distilledEntryIds: newSet };
    }),

  cleanupStaleWorkflows: () =>
    set((state) => {
      // Only filter top-level workflows; children are removed with their parent
      const filteredWorkflows = filterStaleTopLevelWorkflows(state.workflows);
      const filteredOrphans = filterStaleTopLevelWorkflows(
        state.orphanWorkflows,
      );

      // Hide status bar if no workflows remain
      if (
        Object.keys(filteredWorkflows).length === 0 &&
        Object.keys(filteredOrphans).length === 0
      ) {
        clearHideTimer();
        return {
          workflows: filteredWorkflows,
          orphanWorkflows: filteredOrphans,
          statusBarVisible: false,
        };
      }

      return {
        workflows: filteredWorkflows,
        orphanWorkflows: filteredOrphans,
      };
    }),

  startCleanupInterval: () => {
    // Don't start if already running
    if (cleanupTimerId) return;

    cleanupTimerId = setInterval(() => {
      get().cleanupStaleWorkflows();
    }, STALE_CHECK_INTERVAL_MS);
  },

  stopCleanupInterval: () => {
    if (cleanupTimerId) {
      clearInterval(cleanupTimerId);
      cleanupTimerId = null;
    }
  },
}));

// ============================================================================
// Selectors
// ============================================================================

/**
 * Flatten all workflows including children into an array.
 */
function flattenWorkflows(
  workflows: Record<string, WorkflowProgressNode>,
): WorkflowProgressNode[] {
  const result: WorkflowProgressNode[] = [];
  for (const wf of Object.values(workflows)) {
    result.push(wf);
    result.push(...flattenWorkflows(wf.children));
  }
  return result;
}

/** Select all running workflows (including children). */
export const selectRunningWorkflows = (state: WorkflowStoreState) =>
  flattenWorkflows(state.workflows).filter((wf) => wf.status === "running");

/** Select top-level workflows only. */
export const selectTopLevelWorkflows = (state: WorkflowStoreState) =>
  Object.values(state.workflows);

/** Select count of running workflows (including children). */
export const selectRunningCount = (state: WorkflowStoreState) =>
  flattenWorkflows(state.workflows).filter((wf) => wf.status === "running")
    .length;

/** Select a specific workflow by ID (searches tree). */
export const selectWorkflowById =
  (workflowId: string) => (state: WorkflowStoreState) => {
    const found = findWorkflowInTree(state.workflows, workflowId);
    return found?.node ?? null;
  };

/** Check if any workflow of a specific type is running. */
export const selectIsWorkflowTypeRunning =
  (workflowType: string) => (state: WorkflowStoreState) => {
    const allWorkflows = flattenWorkflows(state.workflows);
    return allWorkflows.some(
      (wf) => wf.workflowType === workflowType && wf.status === "running",
    );
  };

/**
 * Check if a SingleFeedIngestion workflow is running for a specific feed.
 * First checks ingestingFeeds (immediate), then workflows.
 */
export const selectIsFeedIngesting =
  (feedId: string | undefined) => (state: WorkflowStoreState) => {
    if (!feedId) return false;
    // Check immediate ingesting set (before SSE kicks in)
    if (state.ingestingFeeds.has(feedId)) return true;
    // Check running workflows
    const allWorkflows = flattenWorkflows(state.workflows);
    return allWorkflows.some(
      (wf) =>
        wf.workflowType === "SingleFeedIngestion" &&
        wf.status === "running" &&
        wf.workflowId.includes(`single-feed-${feedId}`),
    );
  };

/**
 * Check if an entry is being refreshed.
 * First checks refreshingEntries (immediate), then entryProgress in workflows.
 */
export const selectIsEntryRefreshing =
  (entryId: string | undefined) => (state: WorkflowStoreState) => {
    if (!entryId) return false;
    // Check immediate refreshing set (before SSE kicks in)
    if (state.refreshingEntries.has(entryId)) return true;
    // Check entryProgress in running workflows
    const allWorkflows = flattenWorkflows(state.workflows);
    return allWorkflows.some((wf) => {
      if (wf.status !== "running") return false;
      if (
        wf.workflowType !== "ReprocessEntries" &&
        wf.workflowType !== "DomainFetch"
      ) {
        return false;
      }
      const entryProgress = (
        wf as { entryProgress?: Record<string, EntryProgressState> }
      ).entryProgress;
      if (!entryProgress) return false;
      const entry = Object.values(entryProgress).find(
        (e) => e.entryId === entryId,
      );
      return (
        entry !== undefined &&
        entry.status !== "completed" &&
        entry.status !== "error"
      );
    });
  };

/**
 * Check if an entry is being translated.
 * First checks translatingEntries (immediate), then entryProgress in translation workflows.
 */
export const selectIsEntryTranslating =
  (entryId: string | undefined) => (state: WorkflowStoreState) => {
    if (!entryId) return false;
    // Check immediate translating set (before SSE kicks in)
    if (state.translatingEntries.has(entryId)) return true;
    // Check entryProgress in running translation workflows
    const allWorkflows = flattenWorkflows(state.workflows);
    return allWorkflows.some((wf) => {
      if (wf.status !== "running") return false;
      if (wf.workflowType !== "Translation") return false;
      const entryProgress = (
        wf as { entryProgress?: Record<string, EntryProgressState> }
      ).entryProgress;
      if (!entryProgress) return false;
      const entry = Object.values(entryProgress).find(
        (e) => e.entryId === entryId,
      );
      return (
        entry !== undefined &&
        entry.status !== "completed" &&
        entry.status !== "error"
      );
    });
  };

/**
 * Check if an entry has been distilled (summary generated).
 * Returns true if the entry ID is in the distilledEntryIds set.
 */
export const selectIsEntryDistilled =
  (entryId: string | undefined) => (state: WorkflowStoreState) => {
    if (!entryId) return false;
    return state.distilledEntryIds.has(entryId);
  };
