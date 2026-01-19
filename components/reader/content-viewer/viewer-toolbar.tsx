"use client";

import {
  Star,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  Cross,
  CircleSmall,
  Sparkles,
  Download,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { isResearchContextEnabled } from "@/lib/config";
import type { Entry } from "@/lib/types";

interface ViewerToolbarProps {
  entry: Entry;
  isScrolled: boolean;
  refreshing: boolean;
  contextPanelOpen: boolean;
  hasPrevious: boolean;
  hasNext: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  onToggleRead?: (entry: Entry) => void;
  onToggleStar?: (entry: Entry) => void;
  onToggleKeep?: (entry: Entry) => void;
  onRefresh?: (entry: Entry) => void | Promise<void>;
  onContextPanelOpenChange?: (open: boolean) => void;
}

/**
 * Toolbar component for the content viewer.
 *
 * Contains navigation, read/star/keep toggles, and action buttons.
 */
export function ViewerToolbar({
  entry,
  isScrolled,
  refreshing,
  contextPanelOpen,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onToggleRead,
  onToggleStar,
  onToggleKeep,
  onRefresh,
  onContextPanelOpenChange,
}: ViewerToolbarProps) {
  return (
    <div
      className={cn(
        "flex h-11 shrink-0 items-center gap-2 px-4 transition-[border-color] duration-200",
        isScrolled ? "border-b" : "border-b border-transparent",
      )}
    >
      {/* Navigation */}
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onPrevious}
          disabled={!hasPrevious}
        >
          <ChevronLeft className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onNext}
          disabled={!hasNext}
        >
          <ChevronRight className="size-4" />
        </Button>
      </div>

      <div className="flex-1" />

      <Button
        variant="ghost"
        size="icon"
        className={cn("size-8", entry.keep && "text-neutral-500")}
        onClick={() => onToggleKeep?.(entry)}
        title="Keep from auto-cleanup (p)"
      >
        <Cross className={cn("size-4", entry.keep && "fill-current")} />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={() => onToggleRead?.(entry)}
        title={entry.isRead ? "Mark as unread (m)" : "Mark as read (m)"}
      >
        {entry.isRead ? (
          <CircleSmall className="size-4" />
        ) : (
          <CircleSmall className="size-4 fill-current" />
        )}
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className={cn("size-8", entry.isStarred && "text-neutral-500")}
        onClick={() => onToggleStar?.(entry)}
        title="Toggle Starred (s)"
      >
        <Star className={cn("size-4", entry.isStarred && "fill-current")} />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={() => onRefresh?.(entry)}
        disabled={refreshing}
        title="Refetch content"
      >
        <RefreshCw className={cn("size-4", refreshing && "animate-spin")} />
      </Button>

      {isResearchContextEnabled() && (
        <Button
          variant="ghost"
          size="icon"
          className={cn("size-8", contextPanelOpen && "text-primary")}
          onClick={() => onContextPanelOpenChange?.(!contextPanelOpen)}
          title="Toggle context panel"
        >
          <Sparkles className="size-4" />
        </Button>
      )}

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={async () => {
          const res = await fetch(`/api/entries/${entry.id}/markdown`);
          if (!res.ok) return;
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const link = document.createElement("a");
          link.href = url;
          link.download = `${entry.title}.md`;
          link.click();
          URL.revokeObjectURL(url);
        }}
        title="Download as Markdown"
      >
        <Download className="size-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={() => window.open(entry.url, "_blank")}
        title="Open original entry"
      >
        <ExternalLink className="size-4" />
      </Button>
    </div>
  );
}
