/**
 * Hook for managing subscription data and unread counts.
 *
 * @module hooks/use-subscriptions
 */

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import type { FilterMode } from "@/lib/types";
import type { Subscription } from "@/components/reader/subscription-sidebar";
import { useUrlState } from "@/lib/url-state-context";

/** Return value from useSubscriptions hook. */
interface UseSubscriptionsReturn {
  /** List of subscription items for the sidebar. */
  subscriptions: Subscription[];
  /** True during initial load. */
  loading: boolean;
  /** True when refetching in the background. */
  refetching: boolean;
  /** Decrements unread count when an entry is marked as read. */
  updateCountOnRead: (feedId: string) => void;
  /** Updates unread count when read status is toggled. */
  updateCountOnToggleRead: (feedId: string, nowRead: boolean) => void;
  /** Invalidates cache and refetches subscriptions. */
  refetch: () => Promise<void>;
}

/** Fetches subscription tree from the API. */
async function fetchSubscriptions(
  filterMode: FilterMode,
): Promise<Subscription[]> {
  const response = await fetch(`/api/subscriptions?filterMode=${filterMode}`);
  if (!response.ok) {
    throw new Error("Failed to fetch subscriptions");
  }
  return response.json();
}

/**
 * Hook for managing subscription data and state.
 */
export function useSubscriptions(): UseSubscriptionsReturn {
  const queryClient = useQueryClient();
  const { filterMode } = useUrlState();

  const query = useQuery({
    queryKey: ["subscriptions", filterMode],
    queryFn: () => fetchSubscriptions(filterMode),
  });

  // Refetch (invalidate and refetch)
  // Invalidates ALL filterMode caches to ensure fresh data
  const refetch = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
    await query.refetch();
  }, [queryClient, query]);

  // Update subscription counts when an entry is marked as read
  const updateCountOnRead = React.useCallback(
    (feedId: string) => {
      // Only update counts in "unread" filter mode
      if (filterMode !== "unread") return;

      queryClient.setQueryData<Subscription[]>(
        ["subscriptions", filterMode],
        (prev) => {
          if (!prev) return prev;
          return prev.map((sub) => {
            // Update "All Entries"
            if (sub.id === "all" && sub.count && sub.count > 0) {
              return { ...sub, count: sub.count - 1 };
            }
            // Update category containing the feed
            if (sub.type === "category" && sub.children) {
              const hasFeed = sub.children.some(
                (child) => child.id === `feed-${feedId}`,
              );
              if (hasFeed) {
                return {
                  ...sub,
                  count: sub.count && sub.count > 0 ? sub.count - 1 : 0,
                  children: sub.children.map((child) =>
                    child.id === `feed-${feedId}` &&
                    child.count &&
                    child.count > 0
                      ? { ...child, count: child.count - 1 }
                      : child,
                  ),
                };
              }
            }
            return sub;
          });
        },
      );
    },
    [filterMode, queryClient],
  );

  // Update subscription counts when read status is toggled
  const updateCountOnToggleRead = React.useCallback(
    (feedId: string, nowRead: boolean) => {
      // Only update counts in "unread" filter mode
      if (filterMode !== "unread") return;

      const delta = nowRead ? -1 : 1;

      queryClient.setQueryData<Subscription[]>(
        ["subscriptions", filterMode],
        (prev) => {
          if (!prev) return prev;
          return prev.map((sub) => {
            // Update "All Entries"
            if (sub.id === "all" && sub.count !== undefined) {
              const newCount = Math.max(0, sub.count + delta);
              return { ...sub, count: newCount };
            }
            // Update category containing the feed
            if (sub.type === "category" && sub.children) {
              const hasFeed = sub.children.some(
                (child) => child.id === `feed-${feedId}`,
              );
              if (hasFeed) {
                return {
                  ...sub,
                  count:
                    sub.count !== undefined
                      ? Math.max(0, sub.count + delta)
                      : 0,
                  children: sub.children.map((child) =>
                    child.id === `feed-${feedId}` && child.count !== undefined
                      ? { ...child, count: Math.max(0, child.count + delta) }
                      : child,
                  ),
                };
              }
            }
            return sub;
          });
        },
      );
    },
    [filterMode, queryClient],
  );

  return {
    subscriptions: query.data ?? [],
    loading: query.isLoading,
    refetching: query.isFetching && !query.isLoading,
    updateCountOnRead,
    updateCountOnToggleRead,
    refetch,
  };
}

/**
 * Invalidate subscriptions query to trigger a refetch.
 * Call this after modifying feeds or categories.
 */
export function invalidateSubscriptions(
  queryClient: ReturnType<typeof useQueryClient>,
) {
  return queryClient.invalidateQueries({ queryKey: ["subscriptions"] });
}
