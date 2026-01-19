"use client";

import {
  createContext,
  useContext,
  useCallback,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { useSSE, type SSEStatus } from "@/hooks/use-sse";
import { signOut } from "@/lib/auth-client";
import { useAuth } from "@/components/providers/auth-provider";
import { useWorkflowStore } from "@/stores/workflow-store";
import { isAuthEnabled } from "@/lib/config";
import type {
  WorkflowProgress,
  ContentDistillationProgress,
} from "@/lib/temporal";
import { getWorkflowToastMessage } from "@/lib/workflow-toast";
import { createLogger } from "@/lib/logger";

const log = createLogger("sse:provider");

/** Loading spinner icon for toast notifications. */
const LoadingIcon = <Loader2 className="h-4 w-4 animate-spin" />;

interface SSEContextValue {
  status: SSEStatus;
  isConnected: boolean;
  connect: () => void;
  disconnect: () => void;
}

const SSEContext = createContext<SSEContextValue | null>(null);

interface WorkflowStoreSnapshot {
  workflows: Record<
    string,
    { parentWorkflowId?: string; children: Record<string, unknown> }
  >;
  orphanWorkflows: Record<string, { parentWorkflowId?: string }>;
}

/**
 * Find the top-level parent workflow ID for a given workflow.
 * Walks up the tree using parentWorkflowId until reaching a root.
 */
function findTopLevelParentId(
  state: WorkflowStoreSnapshot,
  workflowId: string,
): string | null {
  // Check if this is already a top-level workflow
  if (state.workflows[workflowId]) {
    return workflowId;
  }

  // Search in orphans and walk up
  const orphan = state.orphanWorkflows[workflowId];
  if (orphan?.parentWorkflowId) {
    return findTopLevelParentId(state, orphan.parentWorkflowId);
  }

  // Search in children of all workflows
  const searchInChildren = (
    workflows: Record<
      string,
      { parentWorkflowId?: string; children: Record<string, unknown> }
    >,
  ): string | null => {
    for (const [id, wf] of Object.entries(workflows)) {
      if (wf.children[workflowId]) {
        // Found the parent, now find its top-level
        if (state.workflows[id]) return id;
        return findTopLevelParentId(state, id);
      }
      const found = searchInChildren(
        wf.children as Record<
          string,
          { parentWorkflowId?: string; children: Record<string, unknown> }
        >,
      );
      if (found) return found;
    }
    return null;
  };

  return searchInChildren(state.workflows);
}

/** SSE provider props */
interface SSEProviderProps {
  children: ReactNode;
  /** Whether to enable SSE connection */
  enabled?: boolean;
}

/**
 * SSE provider component.
 *
 * Manages SSE connection and integrates with React Query for cache updates.
 * Update events include workflow progress from Temporal (fetched by API).
 */
export function SSEProvider({ children, enabled = true }: SSEProviderProps) {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const queryClient = useQueryClient();
  const {
    handleWorkflowUpdate,
    setConnectionStatus,
    addDistilledEntryIds,
    startCleanupInterval,
    stopCleanupInterval,
  } = useWorkflowStore();

  // Only enable SSE when authenticated and not loading auth state
  // Skip auth check if authentication is disabled
  const sseEnabled =
    enabled && (isAuthEnabled() ? isAuthenticated && !authLoading : true);

  // Track toast IDs for each workflow (to update loading -> success/error)
  const toastIds = useRef<Map<string, string | number>>(new Map());

  // Track dismissed toast workflow IDs (to avoid re-showing after user closes)
  const dismissedToastIds = useRef<Set<string>>(new Set());

  // Track if we've shown an error toast (to avoid spam on repeated retries)
  const hasShownErrorToast = useRef(false);

  // Show/update toast for a top-level workflow
  const updateWorkflowToast = useCallback((topLevelId: string) => {
    const workflowNode = useWorkflowStore.getState().workflows[topLevelId];
    if (!workflowNode) return;

    const { status } = workflowNode;
    const message = getWorkflowToastMessage(workflowNode);
    const existingToastId = toastIds.current.get(topLevelId);

    // Handle dismiss callback to track user-closed toasts
    const handleDismiss = () => {
      dismissedToastIds.current.add(topLevelId);
      toastIds.current.delete(topLevelId);
    };

    if (status === "running") {
      // Skip if user has dismissed this toast
      if (dismissedToastIds.current.has(topLevelId)) {
        return;
      }
      // Use toast() instead of toast.loading() to support close button
      if (existingToastId) {
        // Update existing loading toast with new progress
        toast(message.title, {
          id: existingToastId,
          description: message.description,
          duration: Infinity,
          icon: LoadingIcon,
          onDismiss: handleDismiss,
        });
      } else {
        // Create new loading toast
        const id = toast(message.title, {
          description: message.description,
          duration: Infinity,
          icon: LoadingIcon,
          onDismiss: handleDismiss,
        });
        toastIds.current.set(topLevelId, id);
      }
    } else if (status === "completed") {
      // Clear dismissed state for this workflow (allow future runs to show)
      dismissedToastIds.current.delete(topLevelId);
      if (existingToastId) {
        toast.success(message.title, {
          id: existingToastId,
          description: message.description,
          duration: 5000,
        });
        toastIds.current.delete(topLevelId);
      } else {
        toast.success(message.title, {
          description: message.description,
          duration: 5000,
        });
      }
    } else if (status === "error") {
      // Clear dismissed state for this workflow (allow future runs to show)
      dismissedToastIds.current.delete(topLevelId);
      if (existingToastId) {
        toast.error(message.title, {
          id: existingToastId,
          description: message.description,
        });
        toastIds.current.delete(topLevelId);
      } else {
        toast.error(message.title, {
          description: message.description,
        });
      }
    }
  }, []);

  // Show toast based on workflow status change
  const showWorkflowToast = useCallback(
    (progress: WorkflowProgress) => {
      // Skip toast if showToast is explicitly false
      if (progress.showToast === false) {
        return;
      }

      const { workflowId, parentWorkflowId } = progress;
      const state = useWorkflowStore.getState();

      // Find the top-level workflow to update its toast
      const topLevelId = parentWorkflowId
        ? findTopLevelParentId(state, parentWorkflowId)
        : workflowId;

      if (topLevelId) {
        updateWorkflowToast(topLevelId);
      }
    },
    [updateWorkflowToast],
  );

  // Fetch all active workflows on connect/reconnect
  const fetchActiveWorkflows = useCallback(async () => {
    try {
      const response = await fetch("/api/workflows/active");
      if (!response.ok) {
        log.warn(
          { status: response.status },
          "failed to fetch active workflows",
        );
        return;
      }
      const workflows = await response.json();
      for (const wf of workflows) {
        if (wf.progress) {
          handleWorkflowUpdate(wf.progress);
        }
      }
    } catch (error) {
      console.error("error fetching active workflows:", error);
    }
  }, [handleWorkflowUpdate]);

  // Handle authentication expiration
  const handleAuthExpired = useCallback(() => {
    log.warn("auth expired, signing out");
    toast.error("Session expired. Please sign in again.");
    // Sign out and redirect to login
    signOut({ fetchOptions: { onSuccess: () => window.location.reload() } });
  }, []);

  // Handle workflow error (Query failed)
  const handleWorkflowError = useCallback(
    (data: { workflowId: string; error: string }) => {
      log.error({ data }, "workflow error");
      const { workflowId, error } = data;

      // Dismiss existing loading toast and show error
      const existingToastId = toastIds.current.get(workflowId);
      if (existingToastId) {
        toast.error("Workflow query failed", {
          id: existingToastId,
          description: error,
        });
        toastIds.current.delete(workflowId);
      } else {
        toast.error("Workflow query failed", {
          description: error,
        });
      }
    },
    [],
  );

  const { status, isConnected, connect, disconnect } = useSSE({
    autoConnect: sseEnabled,

    onUpdate: (data) => {
      log.debug({ data }, "update");
      // Use progress directly from the event (fetched by API from Temporal)
      if (data.progress) {
        const progress = data.progress as WorkflowProgress;

        // Update store first (so children are attached before toast generation)
        handleWorkflowUpdate(progress);

        // Show/update toast for top-level workflow
        showWorkflowToast(progress);

        // Handle ContentDistillation: track completed entries for UI updates
        if (progress.workflowType === "ContentDistillation") {
          const distillProgress = progress as ContentDistillationProgress;
          const completedIds: string[] = [];

          for (const entry of Object.values(distillProgress.entryProgress)) {
            if (entry.status === "completed" && entry.entryId) {
              completedIds.push(entry.entryId);
            }
          }

          if (completedIds.length > 0) {
            addDistilledEntryIds(completedIds);
            // Mark entries cache as stale (without immediate refetch)
            queryClient.invalidateQueries({
              queryKey: ["entries"],
              refetchType: "none",
            });
          }
        }

        // Invalidate caches when workflow completes
        if (progress.status === "completed") {
          queryClient.invalidateQueries({ queryKey: ["entries"] });

          // Invalidate subscriptions (unread counts) for feed ingestion
          if (progress.workflowType === "SingleFeedIngestion") {
            queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
          }
        }
      }
    },

    onKeepAlive: (_data) => {
      // log.debug({ timestamp: new Date(data.timestamp).toISOString() }, "keep-alive");
    },

    onAuthExpired: handleAuthExpired,

    onError: handleWorkflowError,

    onStatusChange: (newStatus) => {
      log.info({ status: newStatus }, "status changed");
      setConnectionStatus(newStatus === "error" ? "disconnected" : newStatus);

      // Show error toast (only once per disconnection)
      if (newStatus === "error" && !hasShownErrorToast.current) {
        hasShownErrorToast.current = true;
        toast.error("Server connection lost", {
          description: "Attempting to reconnect...",
        });
      }

      // On reconnect, fetch active workflows and reset error toast flag
      if (newStatus === "connected") {
        if (hasShownErrorToast.current) {
          hasShownErrorToast.current = false;
          toast.success("Server connection restored");
        }
        fetchActiveWorkflows();
        // Start stale workflow cleanup when connected
        startCleanupInterval();
      } else if (newStatus === "disconnected" || newStatus === "error") {
        // Stop cleanup when disconnected
        stopCleanupInterval();
      }
    },
  });

  // Fetch active workflows on initial mount when connected
  useEffect(() => {
    if (isConnected) {
      fetchActiveWorkflows();
    }
  }, [isConnected, fetchActiveWorkflows]);

  // Cleanup interval on unmount
  useEffect(() => {
    return () => {
      stopCleanupInterval();
    };
  }, [stopCleanupInterval]);

  return (
    <SSEContext.Provider value={{ status, isConnected, connect, disconnect }}>
      {children}
    </SSEContext.Provider>
  );
}

/**
 * Hook to access SSE context.
 */
export function useSSEContext(): SSEContextValue {
  const context = useContext(SSEContext);
  if (!context) {
    throw new Error("useSSEContext must be used within SSEProvider");
  }
  return context;
}
