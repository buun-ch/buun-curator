/**
 * Hook for getting detailed information about selected subscription.
 *
 * Provides subscription metadata and breadcrumb navigation path.
 * For feeds, fetches additional details for refetch functionality.
 *
 * @module hooks/use-selected-subscription-info
 */

"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";
import type { Subscription } from "@/components/reader/subscription-sidebar";
import { useUrlState } from "@/lib/url-state-context";
import { useSubscriptions } from "@/hooks/use-subscriptions";

/** An item in the breadcrumb navigation path. */
export interface BreadcrumbItem {
  /** Subscription ID. */
  id: string;
  /** Display title. */
  title: string;
  /** Item type. */
  type: "category" | "feed" | "special";
}

/** Detailed information about a subscription. */
export interface SubscriptionInfo {
  /** Subscription ID. */
  id: string;
  /** Display title. */
  title: string;
  /** Subscription type. */
  type: "category" | "feed" | "special";
  /** Breadcrumb path (e.g., [Category, Feed] or [Category] or [Special]). */
  breadcrumb: BreadcrumbItem[];
  /** Feed ID (for feeds only). */
  feedId?: string;
  /** Feed URL (for feeds only). */
  feedUrl?: string;
  /** Feed name (for feeds only). */
  feedName?: string;
}

/** API response for feed details. */
interface FeedResponse {
  id: string;
  name: string;
  url: string;
  siteUrl: string | null;
  categoryId: string | null;
  type: string | null;
  options: Record<string, unknown> | null;
  etag: string | null;
  lastModified: string | null;
}

/**
 * Fetches feed details from the API.
 *
 * @param feedId - Feed ID to fetch
 * @returns Feed details
 */
async function fetchFeedDetails(feedId: string): Promise<FeedResponse> {
  const response = await fetch(`/api/feeds/${feedId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch feed details");
  }
  return response.json();
}

/** Internal lookup result for subscription info. */
interface SubscriptionLookup {
  title: string;
  type: "category" | "feed" | "special";
  breadcrumb: BreadcrumbItem[];
}

/**
 * Finds subscription info in the subscription tree.
 *
 * @param subscriptions - Subscription tree to search
 * @param id - Subscription ID to find
 * @returns Lookup result or null if not found
 */
function findSubscriptionInfo(
  subscriptions: Subscription[],
  id: string,
): SubscriptionLookup | null {
  // Handle special cases
  if (id === "all") {
    return {
      title: "All Entries",
      type: "special",
      breadcrumb: [{ id: "all", title: "All Entries", type: "special" }],
    };
  }

  // Search through subscriptions
  for (const sub of subscriptions) {
    if (sub.id === id) {
      return {
        title: sub.title,
        type: sub.type,
        breadcrumb: [{ id: sub.id, title: sub.title, type: sub.type }],
      };
    }
    // Check children (feeds within categories)
    if (sub.children) {
      for (const child of sub.children) {
        if (child.id === id) {
          return {
            title: child.title,
            type: child.type,
            breadcrumb: [
              { id: sub.id, title: sub.title, type: sub.type },
              { id: child.id, title: child.title, type: child.type },
            ],
          };
        }
      }
    }
  }
  return null;
}

/** Return value from the useSelectedSubscriptionInfo hook. */
export interface UseSelectedSubscriptionInfoReturn {
  /** Detailed subscription info or null if not found. */
  info: SubscriptionInfo | null;
  /** True while loading feed details. */
  loading: boolean;
}

/**
 * Hook for getting detailed information about selected subscription.
 *
 * Looks up subscription in the tree and fetches additional feed
 * details when a feed is selected. Used for breadcrumb display
 * and single-feed refresh functionality.
 *
 * @returns Subscription info and loading state
 */
export function useSelectedSubscriptionInfo(): UseSelectedSubscriptionInfoReturn {
  const { selectedSubscription } = useUrlState();
  const { subscriptions } = useSubscriptions();
  // Find basic info from subscription tree
  const basicInfo = React.useMemo(() => {
    return findSubscriptionInfo(subscriptions, selectedSubscription);
  }, [subscriptions, selectedSubscription]);

  // Extract feed ID if this is a feed selection
  const feedId = React.useMemo(() => {
    if (selectedSubscription.startsWith("feed-")) {
      return selectedSubscription.replace("feed-", "");
    }
    return null;
  }, [selectedSubscription]);

  // Fetch feed details if needed
  const feedQuery = useQuery({
    queryKey: ["feed", feedId],
    queryFn: () => fetchFeedDetails(feedId!),
    enabled: !!feedId,
  });

  // Combine info
  const info = React.useMemo((): SubscriptionInfo | null => {
    if (!basicInfo) return null;

    const base: SubscriptionInfo = {
      id: selectedSubscription,
      title: basicInfo.title,
      type: basicInfo.type,
      breadcrumb: basicInfo.breadcrumb,
    };

    // Add feed-specific info if available
    if (feedId && feedQuery.data) {
      base.feedId = feedQuery.data.id;
      base.feedUrl = feedQuery.data.url;
      base.feedName = feedQuery.data.name;
    }

    return base;
  }, [basicInfo, selectedSubscription, feedId, feedQuery.data]);

  return {
    info,
    loading: feedId ? feedQuery.isLoading : false,
  };
}
