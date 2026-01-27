"use client";

import { Inbox, Loader2 } from "lucide-react";
import * as React from "react";

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

import { EntryListItem } from "./entry-list-item";
import { useInfiniteScroll } from "./hooks/use-infinite-scroll";
import { ListHeader } from "./list-header";
import type { ContentListProps } from "./types";

// Re-export types for external use
export type { ContentListProps } from "./types";

/**
 * Content list component displaying entries with filtering and sorting.
 *
 * Supports infinite scroll, search, and keyboard navigation.
 */
export function ContentList({
  entries = [],
  loading = false,
  filterMode = "unread",
  onFilterModeChange,
  sortMode = "newest",
  onSortModeChange,
  hasMore = false,
  loadingMore = false,
  onLoadMore,
  selectedId,
  onSelect,
  onToggleStar,
  subscriptionInfo,
  onRefetch,
  isRefetching = false,
  onMarkAllAsRead,
  isMarkingAllAsRead = false,
  searchQuery = "",
  onSearchQueryChange,
  onBack,
}: ContentListProps) {
  // Refs for entry items (for keyboard navigation focus)
  const entryRefs = React.useRef<Map<string, HTMLDivElement>>(new Map());

  // Focus and scroll to selected entry when it changes (for keyboard navigation)
  React.useEffect(() => {
    if (selectedId) {
      const element = entryRefs.current.get(selectedId);
      if (element) {
        // Only focus if not already focused (avoid stealing focus from other panels)
        if (document.activeElement !== element) {
          element.focus({ preventScroll: true });
        }
        // Scroll into view if needed
        element.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  }, [selectedId]);

  // Infinite scroll hook
  const loadMoreRef = useInfiniteScroll({
    hasMore,
    loadingMore,
    onLoadMore,
  });

  // Check if refetch is available (only for feeds)
  const canRefetch = subscriptionInfo?.type === "feed" && !!onRefetch;

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <ListHeader
        subscriptionInfo={subscriptionInfo}
        filterMode={filterMode}
        onFilterModeChange={onFilterModeChange}
        sortMode={sortMode}
        onSortModeChange={onSortModeChange}
        searchQuery={searchQuery}
        onSearchQueryChange={onSearchQueryChange}
        canRefetch={canRefetch}
        onRefetch={onRefetch}
        isRefetching={isRefetching}
        onMarkAllAsRead={onMarkAllAsRead}
        isMarkingAllAsRead={isMarkingAllAsRead}
        onBack={onBack}
      />

      {/* Entry list */}
      <div className="flex-1 overflow-auto border-t">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : entries.length === 0 ? (
          <Empty className="py-8">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Inbox className="h-5 w-5" />
              </EmptyMedia>
              <EmptyTitle>No Entries</EmptyTitle>
              <EmptyDescription>
                No entries match the current filter.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="divide-y">
            {entries.map((entry) => (
              <EntryListItem
                key={entry.id}
                ref={(el) => {
                  if (el) {
                    entryRefs.current.set(entry.id, el);
                  } else {
                    entryRefs.current.delete(entry.id);
                  }
                }}
                entry={entry}
                isSelected={selectedId === entry.id}
                onSelect={onSelect}
                onToggleStar={onToggleStar}
              />
            ))}
            {/* Infinite scroll trigger */}
            {hasMore && (
              <div
                ref={loadMoreRef}
                className="flex items-center justify-center py-4"
              >
                {loadingMore ? (
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                ) : (
                  <span className="text-xs text-muted-foreground">
                    Scroll for more
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
