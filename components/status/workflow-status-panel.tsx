"use client";

/**
 * Workflow status panel component.
 *
 * Shows detailed workflow progress in an expandable panel.
 * Similar to React Query DevTools.
 *
 * @module components/sse/workflow-status-panel
 */

import { useCallback, useRef } from "react";
import { useWorkflowStore } from "@/stores/workflow-store";
import type { WorkflowProgressNode } from "@/lib/temporal";
import { cn } from "@/lib/utils";
import {
  X,
  CheckCircle,
  XCircle,
  Loader2,
  Trash2,
  Workflow,
  CircleSmall,
} from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Workflow status panel that shows detailed workflow progress.
 *
 * Expands from the bottom of the screen like React Query DevTools.
 * Supports drag-to-resize from the top edge.
 */
export function WorkflowStatusPanel() {
  const workflows = useWorkflowStore((state) => state.workflows);
  const panelOpen = useWorkflowStore((state) => state.panelOpen);
  const setPanelOpen = useWorkflowStore((state) => state.setPanelOpen);
  const removeWorkflow = useWorkflowStore((state) => state.removeWorkflow);
  const clearFinished = useWorkflowStore((state) => state.clearFinished);
  const connectionStatus = useWorkflowStore((state) => state.connectionStatus);
  const panelHeight = useWorkflowStore((state) => state.panelHeight);
  const setPanelHeight = useWorkflowStore((state) => state.setPanelHeight);

  // Track resize state
  const isResizing = useRef(false);
  const startY = useRef(0);
  const startHeight = useRef(0);

  // Handle resize drag start
  const handleResizeStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      isResizing.current = true;
      startY.current = e.clientY;
      startHeight.current = panelHeight;

      const handleMouseMove = (e: MouseEvent) => {
        if (!isResizing.current) return;
        // Dragging up increases height, dragging down decreases
        const delta = startY.current - e.clientY;
        setPanelHeight(startHeight.current + delta);
      };

      const handleMouseUp = () => {
        isResizing.current = false;
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
    },
    [panelHeight, setPanelHeight],
  );

  // Get all workflows sorted by startedAt (most recent first)
  const allWorkflows = Object.values(workflows).sort(
    (a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime(),
  );

  const hasFinished = allWorkflows.some(
    (wf) => wf.status === "completed" || wf.status === "error",
  );

  if (!panelOpen) {
    return null;
  }

  return (
    <div
      className={cn(
        "fixed right-0 bottom-0 left-0 z-40",
        "border-t border-border bg-background/95 backdrop-blur",
        "shadow-lg",
      )}
      style={{ height: panelHeight }}
    >
      {/* Resize handle */}
      <div
        className={cn(
          "absolute -top-1 right-0 left-0 h-2",
          "cursor-ns-resize",
          "flex items-center justify-center",
          "transition-colors hover:bg-accent/50",
        )}
        onMouseDown={handleResizeStart}
      ></div>

      {/* Header */}
      <div className="flex h-9 items-center justify-between border-b border-border px-3">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Workflow className="h-4 w-4" />
          <CircleSmall
            className={cn(
              "h-4 w-4",
              connectionStatus === "connected" && "fill-muted-foreground",
              connectionStatus === "connecting" &&
                "animate-pulse fill-muted-foreground",
              connectionStatus === "disconnected" && "",
            )}
          />
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={clearFinished}
            disabled={!hasFinished}
          >
            <Trash2
              className={cn("h-4 w-4", !hasFinished && "text-muted-foreground")}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setPanelOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="h-[calc(100%-2.25rem)] overflow-y-auto">
        {allWorkflows.length === 0 ? (
          <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
            No active workflows
          </div>
        ) : (
          <div className="divide-y divide-border">
            {allWorkflows.map((workflow) => (
              <WorkflowItem
                key={workflow.workflowId}
                workflow={workflow}
                onRemove={() => removeWorkflow(workflow.workflowId)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface WorkflowItemProps {
  workflow: WorkflowProgressNode;
  onRemove: () => void;
}

function WorkflowItem({ workflow, onRemove }: WorkflowItemProps) {
  const statusIcons = {
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />,
    completed: <CheckCircle className="h-4 w-4 text-green-500" />,
    error: <XCircle className="h-4 w-4 text-red-500" />,
  };
  const statusIcon = statusIcons[workflow.status];

  const workflowLabel = getWorkflowLabel(workflow.workflowType);
  const durationMs =
    new Date(workflow.updatedAt).getTime() -
    new Date(workflow.startedAt).getTime();
  const duration = formatDuration(durationMs);

  // Extract feedName from workflow-specific fields (if present)
  const feedName =
    "feedName" in workflow
      ? (workflow as { feedName?: string }).feedName
      : undefined;

  return (
    <div className="group flex items-center gap-3 px-3 py-2 hover:bg-muted/50">
      {/* Status icon */}
      <div className="flex-shrink-0">{statusIcon}</div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">
            {workflowLabel}
            {feedName && (
              <span className="ml-1 font-normal text-muted-foreground">
                ({feedName})
              </span>
            )}
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {workflow.status === "running" && workflow.message && (
            <span className="truncate">{workflow.message}</span>
          )}
          {workflow.status === "error" && (
            <span className="truncate text-red-500" title={workflow.error}>
              {workflow.error}
            </span>
          )}
          <span className="ml-auto">{duration}</span>
        </div>

        {/* Running indicator for active workflows */}
        {workflow.status === "running" && (
          <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-muted">
            <div className="h-full w-full animate-pulse bg-blue-500" />
          </div>
        )}
      </div>

      {/* Remove button (show on hover for finished workflows) */}
      {workflow.status !== "running" && (
        <Button
          variant="ghost"
          size="icon"
          className="h-6 w-6 opacity-0 group-hover:opacity-100"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        >
          <X className="h-3 w-3" />
        </Button>
      )}
    </div>
  );
}

/** Get human-readable workflow label. */
function getWorkflowLabel(workflowType: string): string {
  switch (workflowType) {
    case "SingleFeedIngestion":
      return "Feed Ingestion";
    case "ReprocessEntries":
      return "Reprocess Entries";
    case "AllFeedsIngestion":
      return "All Feeds Ingestion";
    default:
      return workflowType;
  }
}

/** Format duration in human-readable format. */
function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds}s`;
}
