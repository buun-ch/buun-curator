/**
 * Hook for managing selected entry state and navigation.
 *
 * Handles entry selection, detail fetching via TanStack Query,
 * read status updates, and keyboard navigation between entries.
 *
 * @module hooks/use-selected-entry
 */

"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { type Entry, type EntryListItem } from "@/lib/types";
import { useEntry, useUpdateEntry } from "./use-entry";

/** Options for the useSelectedEntry hook. */
interface UseSelectedEntryOptions {
  /** Current list of entries for navigation (lightweight list items). */
  entries: EntryListItem[];
  /** Function to update the entries list. */
  setEntries: (
    updater: EntryListItem[] | ((prev: EntryListItem[]) => EntryListItem[]),
  ) => void;
  /** Callback when an entry is marked as read (feedId for subscription count update). */
  onMarkAsRead?: (feedId: string) => void;
  /** Callback when an entry is marked as read (entryId for preserving in unread mode). */
  onPreserveEntry?: (entryId: string) => void;
}

/** Return value from the useSelectedEntry hook. */
interface UseSelectedEntryReturn {
  /** Currently selected entry with full details (includes content and labels). */
  selectedEntry: Entry | null;
  /** Function to update the selected entry in cache. */
  setSelectedEntry: React.Dispatch<React.SetStateAction<Entry | null>>;
  /** True while loading entry details. */
  loading: boolean;
  /** Selects an entry and fetches its full details. */
  selectEntry: (entry: EntryListItem) => void;
  /** True if there's a previous entry to navigate to. */
  hasPrevious: boolean;
  /** True if there's a next entry to navigate to. */
  hasNext: boolean;
  /** Navigates to the previous entry. */
  goToPrevious: () => void;
  /** Navigates to the next entry. */
  goToNext: () => void;
}

/**
 * Hook for managing selected entry state and navigation.
 *
 * Uses TanStack Query for entry data caching. When an entry is selected,
 * its full details are fetched and cached. Automatically marks entries
 * as read when selected.
 *
 * @param options - Hook options including entries list and callbacks
 * @returns Selected entry state and navigation functions
 */
export function useSelectedEntry({
  entries,
  setEntries,
  onMarkAsRead,
  onPreserveEntry,
}: UseSelectedEntryOptions): UseSelectedEntryReturn {
  const queryClient = useQueryClient();

  // Track selected entry ID and similarity score (from list)
  const [selectedEntryId, setSelectedEntryId] = React.useState<string | null>(
    null,
  );
  const [similarityScore, setSimilarityScore] = React.useState<
    number | undefined
  >(undefined);

  // Track if we've marked the current entry as read (to avoid duplicate mutations)
  const markedAsReadRef = React.useRef<string | null>(null);

  // Fetch entry data via TanStack Query
  const { entry: fetchedEntry, isLoading } = useEntry(selectedEntryId);

  // Mutation for marking entry as read
  const updateEntry = useUpdateEntry({
    onSuccess: async (entryId) => {
      // Update entries list
      setEntries((prev) =>
        prev.map((e) => (e.id === entryId ? { ...e, isRead: true } : e)),
      );

      // Notify parent to update subscription counts
      const entry = queryClient.getQueryData<Entry>(["entry", entryId]);
      if (entry?.feedId && onMarkAsRead) {
        onMarkAsRead(entry.feedId);
      }

      // Track entry for preserving in unread mode
      onPreserveEntry?.(entryId);

      // Mark all entry caches as stale (without immediate refetch)
      await queryClient.invalidateQueries({
        queryKey: ["entries"],
        refetchType: "none",
      });
    },
    onError: (error) => {
      console.error("Failed to mark entry as read:", error);
      markedAsReadRef.current = null; // Allow retry
    },
  });

  // Merge fetched entry with similarity score
  const selectedEntry = React.useMemo(() => {
    if (!fetchedEntry) return null;
    if (similarityScore !== undefined) {
      return { ...fetchedEntry, similarityScore };
    }
    return fetchedEntry;
  }, [fetchedEntry, similarityScore]);

  // Mark entry as read when it's loaded
  React.useEffect(() => {
    if (!selectedEntry || !selectedEntryId) return;
    if (selectedEntry.isRead) return;
    if (markedAsReadRef.current === selectedEntryId) return;

    // Mark as read via mutation
    markedAsReadRef.current = selectedEntryId;
    updateEntry.mutate({ entryId: selectedEntryId, data: { isRead: true } });
  }, [selectedEntry, selectedEntryId, updateEntry]);

  // Select an entry (just sets the ID, query handles fetching)
  const selectEntry = React.useCallback((entry: EntryListItem) => {
    setSelectedEntryId(entry.id);
    setSimilarityScore(entry.similarityScore);
    markedAsReadRef.current = null; // Reset for new entry
  }, []);

  // setSelectedEntry - updates the query cache directly
  const setSelectedEntry = React.useCallback<
    React.Dispatch<React.SetStateAction<Entry | null>>
  >(
    (action) => {
      if (!selectedEntryId) return;

      queryClient.setQueryData<Entry>(["entry", selectedEntryId], (old) => {
        if (typeof action === "function") {
          return action(old ?? null) ?? undefined;
        }
        return action ?? undefined;
      });
    },
    [selectedEntryId, queryClient],
  );

  // Entry navigation
  const selectedIndex = selectedEntryId
    ? entries.findIndex((e) => e.id === selectedEntryId)
    : -1;
  const hasPrevious = selectedIndex > 0;
  const hasNext = selectedIndex < entries.length - 1 && selectedIndex >= 0;

  const goToPrevious = React.useCallback(() => {
    if (hasPrevious) {
      selectEntry(entries[selectedIndex - 1]);
    } else if (selectedIndex === -1 && entries.length > 0) {
      selectEntry(entries[0]);
    }
  }, [hasPrevious, selectedIndex, entries, selectEntry]);

  const goToNext = React.useCallback(() => {
    if (hasNext) {
      selectEntry(entries[selectedIndex + 1]);
    } else if (selectedIndex === -1 && entries.length > 0) {
      selectEntry(entries[0]);
    }
  }, [hasNext, selectedIndex, entries, selectEntry]);

  return {
    selectedEntry,
    setSelectedEntry,
    loading: isLoading,
    selectEntry,
    hasPrevious,
    hasNext,
    goToPrevious,
    goToNext,
  };
}
