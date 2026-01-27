"use client";

import { Bug, Loader2, Play, RefreshCw, Sparkles, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { ViewMode } from "./types";

interface ContextPanelHeaderProps {
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  extracting: boolean;
  loading: boolean;
  entryId?: string;
  onStartExtraction: () => void;
  onRefresh: () => void;
  onClose: () => void;
}

/**
 * Header component for the context panel.
 *
 * Contains view mode toggle, action buttons, and close button.
 */
export function ContextPanelHeader({
  viewMode,
  onViewModeChange,
  extracting,
  loading,
  entryId,
  onStartExtraction,
  onRefresh,
  onClose,
}: ContextPanelHeaderProps) {
  return (
    <div className="flex h-10 shrink-0 items-center justify-between border-b px-4">
      <div className="flex items-center gap-1">
        {/* View mode toggle */}
        <Button
          variant="ghost"
          size="icon"
          className={cn("size-7", viewMode === "context" && "bg-accent")}
          onClick={() => onViewModeChange("context")}
          title="Context view"
        >
          <Sparkles
            className={cn(
              "h-4 w-4",
              extracting
                ? "animate-pulse text-primary"
                : viewMode === "context"
                  ? "text-primary"
                  : "text-muted-foreground",
            )}
          />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn("size-7", viewMode === "debug" && "bg-accent")}
          onClick={() => onViewModeChange("debug")}
          title="Debug view"
        >
          <Bug
            className={cn(
              "h-4 w-4",
              viewMode === "debug" ? "text-primary" : "text-muted-foreground",
            )}
          />
        </Button>
        {extracting && (
          <span className="ml-2 text-xs text-muted-foreground">
            Collecting...
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onStartExtraction}
          disabled={extracting || loading || !entryId}
          title="Run context collection"
        >
          {extracting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onRefresh}
          disabled={loading || extracting || !entryId}
          title="Refresh"
        >
          {loading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="h-4 w-4" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-7"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
