/**
 * Hook for managing entry list data and infinite scroll.
 *
 * Provides entry fetching with pagination, optimistic updates,
 * and cache management using TanStack Query.
 *
 * @module hooks/use-entries
 */

"use client";

import * as React from "react";
import {
  useInfiniteQuery,
  useQueryClient,
  type InfiniteData,
} from "@tanstack/react-query";
import {
  type EntryListItem,
  type FilterMode,
  type SortMode,
  type EntriesConnection,
  normalizeEntryListItem,
} from "@/lib/types";
import { useUrlState } from "@/lib/url-state-context";
import { createLogger } from "@/lib/logger";

const log = createLogger("hooks:entries");

/** Options for the useEntries hook. */
interface UseEntriesOptions {
  /** The subscription ID to fetch entries for (feed-*, category-*, or "all"). */
  selectedSubscription: string;
  /** Entry IDs to preserve in unread mode (entries marked as read during session). */
  preserveIds?: Set<string>;
}

/** Return value from the useEntries hook. */
interface UseEntriesReturn {
  /** Current list of entries (lightweight, no content/labels). */
  entries: EntryListItem[];
  /** Updates the entries list (for optimistic updates). */
  setEntries: (
    updater: EntryListItem[] | ((prev: EntryListItem[]) => EntryListItem[])
  ) => void;
  /** True during initial data load. */
  loading: boolean;
  /** True when refetching in the background. */
  refetching: boolean;
  /** Total count of matching entries. */
  total: number;
  /** Updates the total count. */
  setTotal: React.Dispatch<React.SetStateAction<number>>;
  /** True if more entries can be loaded. */
  hasMore: boolean;
  /** True while loading more entries. */
  loadingMore: boolean;
  /** Loads the next page of entries. */
  loadMore: () => Promise<void>;
  /** Invalidates cache and refetches entries. */
  refetch: () => Promise<void>;
  /** Marks all entries in current view as read. */
  markAllAsRead: () => Promise<void>;
  /** True while marking all as read. */
  isMarkingAllAsRead: boolean;
  /** Current query key for cache operations. */
  queryKey: readonly string[];
}

/**
 * Builds query params for the entries API endpoint.
 *
 * @param selectedSubscription - The subscription ID (feed-*, category-*, or "all")
 * @param filterMode - The filter mode (all, unread, starred)
 * @param sortMode - The sort mode (newest, oldest)
 * @param after - Pagination cursor for the next page
 * @param preserveIds - Entry IDs to preserve in unread mode
 * @returns URLSearchParams configured for the entries API
 */
function buildEntriesParams(
  selectedSubscription: string,
  filterMode: FilterMode,
  sortMode: SortMode,
  after?: string | null,
  preserveIds?: Set<string>
): URLSearchParams {
  const params = new URLSearchParams();

  // Subscription filter
  if (selectedSubscription.startsWith("feed-")) {
    const feedId = selectedSubscription.replace("feed-", "");
    params.set("feedId", feedId);
  } else if (selectedSubscription.startsWith("category-")) {
    const categoryId = selectedSubscription.replace("category-", "");
    params.set("categoryId", categoryId);
  }
  // "all" doesn't need special subscription params

  // Filter mode
  if (filterMode === "starred") {
    params.set("starredOnly", "true");
  } else if (filterMode === "unread") {
    params.set("unreadOnly", "true");
    // Include preserveIds only in unread mode
    if (preserveIds && preserveIds.size > 0) {
      params.set("preserveIds", Array.from(preserveIds).join(","));
    }
  }
  // "all" doesn't need filter params

  // Sort mode
  if (sortMode && sortMode !== "newest") {
    params.set("sort", sortMode);
  }
  // "newest" is the default, no need to set

  if (after) {
    params.set("after", after);
  }

  return params;
}

/**
 * Fetches a page of entries from the API.
 *
 * @param selectedSubscription - The subscription ID to fetch for
 * @param filterMode - The filter mode for entries
 * @param sortMode - The sort mode for entries
 * @param pageParam - Pagination cursor from previous page
 * @param preserveIds - Entry IDs to preserve in unread mode
 * @returns Connection object with entries and pagination info
 */
async function fetchEntriesPage(
  selectedSubscription: string,
  filterMode: FilterMode,
  sortMode: SortMode,
  pageParam?: string | null,
  preserveIds?: Set<string>
): Promise<EntriesConnection> {
  const params = buildEntriesParams(
    selectedSubscription,
    filterMode,
    sortMode,
    pageParam,
    preserveIds
  );
  const url = "/api/entries" + (params.toString() ? "?" + params : "");

  log.debug(
    {
      filterMode,
      preserveIds: preserveIds ? Array.from(preserveIds) : [],
      pageParam: pageParam ?? null,
    },
    "fetchEntriesPage",
  );

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error("Failed to fetch entries");
  }
  return response.json();
}

/**
 * Hook for managing entry list data with infinite scroll.
 *
 * Uses TanStack Query's useInfiniteQuery for pagination and cache
 * management. Supports optimistic updates for entry state changes.
 *
 * @param options - Hook options including subscription, filter, and sort
 * @returns Entry list state and control functions
 */
export function useEntries({
  selectedSubscription,
  preserveIds,
}: UseEntriesOptions): UseEntriesReturn {
  const queryClient = useQueryClient();
  const { filterMode, sortMode } = useUrlState();
  const [total, setTotal] = React.useState(0);

  const [isMarkingAllAsRead, setIsMarkingAllAsRead] = React.useState(false);

  // Store preserveIds in a ref so queryFn always uses the latest value
  // without requiring queryKey changes (which would cause cache fragmentation)
  const preserveIdsRef = React.useRef(preserveIds);
  React.useEffect(() => {
    log.debug(
      { preserveIds: preserveIds ? Array.from(preserveIds) : [] },
      "updating preserveIdsRef",
    );
    preserveIdsRef.current = preserveIds;
  }, [preserveIds]);

  const queryKey = React.useMemo(
    () => ["entries", selectedSubscription, filterMode, sortMode] as const,
    [selectedSubscription, filterMode, sortMode]
  );

  const {
    data,
    isLoading,
    isFetching,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch: queryRefetch,
  } = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam }) =>
      fetchEntriesPage(selectedSubscription, filterMode, sortMode, pageParam, preserveIdsRef.current),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) =>
      lastPage.pageInfo.hasNextPage ? lastPage.pageInfo.endCursor : undefined,
    enabled: selectedSubscription.length > 0,
  });

  // Update total count when data changes
  React.useEffect(() => {
    if (data?.pages[0]) {
      setTotal(data.pages[0].totalCount);
    }
  }, [data?.pages]);

  // Flatten pages into entries array
  const entries = React.useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) =>
      page.edges.map((edge) => normalizeEntryListItem(edge.node))
    );
  }, [data?.pages]);

  // Set entries by updating cache
  const setEntries = React.useCallback(
    (updater: EntryListItem[] | ((prev: EntryListItem[]) => EntryListItem[])) => {
      queryClient.setQueryData<InfiniteData<EntriesConnection>>(
        queryKey,
        (oldData) => {
          if (!oldData) return oldData;

          const currentEntries = oldData.pages.flatMap((page) =>
            page.edges.map((edge) => normalizeEntryListItem(edge.node))
          );

          const newEntries =
            typeof updater === "function" ? updater(currentEntries) : updater;

          // Create a map of updated entries for quick lookup
          const entriesMap = new Map(newEntries.map((e) => [e.id, e]));

          // Rebuild pages with updated entries (list fields only)
          const newPages = oldData.pages.map((page) => ({
            ...page,
            edges: page.edges.map((edge) => {
              const entry = entriesMap.get(edge.node.id);
              if (!entry) return edge;
              return {
                ...edge,
                node: {
                  ...edge.node,
                  isStarred: entry.isStarred,
                  isRead: entry.isRead,
                  keep: entry.keep,
                  summary: entry.summary,
                },
              };
            }),
          }));

          return {
            ...oldData,
            pages: newPages,
          };
        }
      );
    },
    [queryClient, queryKey]
  );

  // Load more entries
  const loadMore = React.useCallback(async () => {
    if (isFetchingNextPage || !hasNextPage) return;
    await fetchNextPage();
  }, [isFetchingNextPage, hasNextPage, fetchNextPage]);

  // Refetch (reset and refetch)
  // Resets ALL entry caches to ensure fresh data across all subscriptions
  const refetch = React.useCallback(async () => {
    await queryClient.resetQueries({
      queryKey: ["entries"],
    });
  }, [queryClient]);

  // Mark all as read
  const markAllAsRead = React.useCallback(async () => {
    setIsMarkingAllAsRead(true);
    try {
      const body: { feedId?: string; categoryId?: string } = {};

      if (selectedSubscription.startsWith("feed-")) {
        body.feedId = selectedSubscription.replace("feed-", "");
      } else if (selectedSubscription.startsWith("category-")) {
        body.categoryId = selectedSubscription.replace("category-", "");
      }
      // "all" doesn't need any filter - marks everything as read

      const response = await fetch("/api/entries/mark-all-read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        throw new Error("Failed to mark all as read");
      }

      // Invalidate ALL entry caches (regardless of filterMode/sortMode)
      // to ensure stale data doesn't appear when switching filters
      await queryClient.invalidateQueries({
        queryKey: ["entries", selectedSubscription],
      });
      // Also invalidate subscriptions to update unread counts
      await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    } finally {
      setIsMarkingAllAsRead(false);
    }
  }, [selectedSubscription, queryClient]);

  return {
    entries,
    setEntries,
    loading: isLoading,
    refetching: isFetching && !isLoading && !isFetchingNextPage,
    total,
    setTotal,
    hasMore: hasNextPage ?? false,
    loadingMore: isFetchingNextPage,
    loadMore,
    refetch,
    markAllAsRead,
    isMarkingAllAsRead,
    queryKey,
  };
}
