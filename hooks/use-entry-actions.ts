/**
 * Hook for entry actions like starring, keep, and content refresh.
 *
 * Provides optimistic updates for immediate UI feedback with
 * automatic rollback on API errors. Refresh state is tracked via
 * workflow store for accurate loading indicators.
 *
 * @module hooks/use-entry-actions
 */

"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useWorkflowStore } from "@/stores/workflow-store";
import { type Entry, type EntryListItem } from "@/lib/types";
import { useUpdateEntry } from "./use-entry";

/** Options for the useEntryActions hook. */
interface UseEntryActionsOptions {
  /** Function to update the entries list (lightweight list items). */
  setEntries: (
    updater: EntryListItem[] | ((prev: EntryListItem[]) => EntryListItem[]),
  ) => void;
  /** Callback to update subscription counts when read status changes. */
  onToggleRead?: (feedId: string, nowRead: boolean) => void;
  /** Callback when an entry is marked as read (for preserving in unread mode). */
  onMarkAsRead?: (entryId: string) => void;
}

/** Return value from the useEntryActions hook. */
interface UseEntryActionsReturn {
  /** Toggles the starred status of an entry (accepts list item or full entry). */
  toggleStar: (entry: EntryListItem) => void;
  /** Toggles the keep status (accepts list item or full entry). */
  toggleKeep: (entry: EntryListItem) => void;
  /** Toggles the read/unread status of an entry (accepts list item or full entry). */
  toggleRead: (entry: EntryListItem) => void;
  /** Triggers content refresh via Temporal workflow (requires full entry). */
  refreshEntry: (entry: Entry) => Promise<void>;
}

/**
 * Truncates a title for toast notification display.
 *
 * @param title - The title to truncate
 * @param maxLength - Maximum length before truncation
 * @returns Truncated title with ellipsis if needed
 */
function truncateTitle(title: string, maxLength: number = 30): string {
  if (title.length <= maxLength) return title;
  return title.slice(0, maxLength) + "...";
}

/**
 * Hook for entry actions with optimistic updates.
 *
 * Handles starring, keep status, and content refresh.
 * Uses TanStack Query mutations for API calls with optimistic updates.
 *
 * @param options - Hook options with state setters
 * @returns Action functions and loading states
 */
export function useEntryActions({
  setEntries,
  onToggleRead,
  onMarkAsRead,
}: UseEntryActionsOptions): UseEntryActionsReturn {
  const queryClient = useQueryClient();
  const addRefreshingEntry = useWorkflowStore(
    (state) => state.addRefreshingEntry,
  );

  // Mutation for updating entry fields
  const updateEntry = useUpdateEntry();

  // Toggle star status
  const toggleStar = React.useCallback(
    (entry: EntryListItem) => {
      const newStarred = !entry.isStarred;

      // Optimistic update for entries list
      setEntries((prev) =>
        prev.map((e) =>
          e.id === entry.id ? { ...e, isStarred: newStarred } : e,
        ),
      );

      // Mutation handles entry cache update with automatic rollback
      updateEntry.mutate(
        { entryId: entry.id, data: { isStarred: newStarred } },
        {
          onError: () => {
            // Revert entries list on error
            setEntries((prev) =>
              prev.map((e) =>
                e.id === entry.id ? { ...e, isStarred: !newStarred } : e,
              ),
            );
          },
        },
      );
    },
    [setEntries, updateEntry],
  );

  // Toggle read/unread status
  const toggleRead = React.useCallback(
    (entry: EntryListItem) => {
      const newIsRead = !entry.isRead;

      // Optimistic update for entries list
      setEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, isRead: newIsRead } : e)),
      );

      // Update subscription counts optimistically
      onToggleRead?.(entry.feedId, newIsRead);

      // Track entry for preserving in unread mode when marked as read
      if (newIsRead) {
        onMarkAsRead?.(entry.id);
      }

      // Mutation handles entry cache update with automatic rollback
      updateEntry.mutate(
        { entryId: entry.id, data: { isRead: newIsRead } },
        {
          onSuccess: async () => {
            // Mark all entry caches as stale (without immediate refetch)
            await queryClient.invalidateQueries({
              queryKey: ["entries"],
              refetchType: "none",
            });
          },
          onError: () => {
            // Revert entries list on error
            setEntries((prev) =>
              prev.map((e) =>
                e.id === entry.id ? { ...e, isRead: !newIsRead } : e,
              ),
            );
            // Revert subscription counts
            onToggleRead?.(entry.feedId, !newIsRead);
          },
        },
      );
    },
    [onMarkAsRead, onToggleRead, queryClient, setEntries, updateEntry],
  );

  // Toggle keep status (true = preserve from auto-cleanup)
  const toggleKeep = React.useCallback(
    (entry: EntryListItem) => {
      const newKeep = !entry.keep;

      // Optimistic update for entries list
      setEntries((prev) =>
        prev.map((e) => (e.id === entry.id ? { ...e, keep: newKeep } : e)),
      );

      // Mutation handles entry cache update with automatic rollback
      updateEntry.mutate(
        { entryId: entry.id, data: { keep: newKeep } },
        {
          onError: () => {
            // Revert entries list on error
            setEntries((prev) =>
              prev.map((e) =>
                e.id === entry.id ? { ...e, keep: !newKeep } : e,
              ),
            );
          },
        },
      );
    },
    [setEntries, updateEntry],
  );

  // Refresh entry content via Temporal workflow
  // Toast notifications and completion handling are done via SSE in sse-provider.tsx
  const refreshEntry = React.useCallback(
    async (entry: Entry) => {
      const entryId = entry.id;
      const shortTitle = truncateTitle(entry.title);

      // Add to workflow store for immediate loading feedback
      addRefreshingEntry(entryId);

      try {
        // Trigger the Temporal workflow
        const refetchResponse = await fetch(`/api/entries/${entryId}/refetch`, {
          method: "POST",
        });

        if (!refetchResponse.ok) {
          throw new Error("Failed to start refetch workflow");
        }

        const refetchData = await refetchResponse.json();

        // Handle case where content was cleared (fetchContent: false)
        if (refetchData.cleared) {
          // Invalidate the entry query to refetch with cleared content
          await queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
          // Note: No need to remove - workflow store cleanup is automatic
          return;
        }

        // Workflow started successfully - SSE will handle progress updates
        // Cleanup is automatic via handleWorkflowUpdate when entry completes
      } catch (error) {
        console.error("Failed to refresh entry:", error);
        toast.error(`Failed: ${shortTitle}`);
        // Note: Entry stays in refreshingEntries but that's OK - it will be
        // cleaned up on next successful workflow update, or user can retry
      }
    },
    [addRefreshingEntry, queryClient],
  );

  return {
    toggleStar,
    toggleKeep,
    toggleRead,
    refreshEntry,
  };
}
