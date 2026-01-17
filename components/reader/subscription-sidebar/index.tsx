"use client";

import * as React from "react";
import { useState, useCallback } from "react";
import { Plus, Rss, Settings } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { useFeedIngestion } from "@/hooks/use-feed-ingestion";
import { useUrlState } from "@/lib/url-state-context";
import { usePreserveEntries } from "@/lib/preserve-entries-context";
import { UserMenu } from "./user-menu";
import { isRedditEnabled } from "@/lib/config";
import { SSEStatusIndicator } from "@/components/status";

import type { SubscriptionSidebarProps } from "./types";
import { SidebarHeader } from "./sidebar-header";
import { FeedsSection } from "./feeds-section";
import { RedditSection } from "./reddit-section";

// Re-export types for external use
export type { Subscription, SubscriptionSidebarProps } from "./types";

/**
 * Subscription sidebar component.
 *
 * Displays hierarchical feed subscriptions and Reddit favorites.
 */
export function SubscriptionSidebar({
  collapsed = false,
  onCollapsedChange,
  viewMode = "reader",
  onFetchNewComplete,
}: SubscriptionSidebarProps) {
  // URL state for navigation
  const {
    selectedSubscription: selectedId,
    navigateToAllEntries,
    navigateToCategory,
    navigateToFeed,
    navigateToRedditHome,
    navigateToRedditSearch,
    navigateToRedditFavorites,
    navigateToSubreddit,
    navigateToSettings,
  } = useUrlState();

  // Handle selection - navigate via URL
  const onSelect = useCallback(
    (id: string) => {
      if (id === "all") {
        navigateToAllEntries();
      } else if (id.startsWith("feed-")) {
        navigateToFeed(id.slice(5));
      } else if (id.startsWith("category-")) {
        navigateToCategory(id.slice(9));
      } else if (id === "reddit" || id === "reddit-home") {
        navigateToRedditHome();
      } else if (id === "reddit-search" || id.startsWith("reddit-search-")) {
        navigateToRedditSearch();
      } else if (id === "reddit-favorites") {
        navigateToRedditFavorites();
      } else if (id.startsWith("reddit-fav-")) {
        navigateToSubreddit(id.slice(11));
      }
    },
    [
      navigateToAllEntries,
      navigateToCategory,
      navigateToFeed,
      navigateToRedditHome,
      navigateToRedditSearch,
      navigateToRedditFavorites,
      navigateToSubreddit,
    ]
  );

  // Subscriptions data
  const {
    subscriptions,
    loading,
    refetching,
    refetch: refetchSubscriptions,
  } = useSubscriptions();

  // Preserve entries context
  const { clearPreserveIds } = usePreserveEntries();

  // Wrap refetch to also update entry list
  const handleRefresh = React.useCallback(async () => {
    clearPreserveIds();
    await refetchSubscriptions();
    await onFetchNewComplete?.();
  }, [clearPreserveIds, refetchSubscriptions, onFetchNewComplete]);

  // Feed ingestion workflow
  const { isFetchingNew, handleFetchNew } = useFeedIngestion({
    onStart: refetchSubscriptions,
    onComplete: async () => {
      await refetchSubscriptions();
      await onFetchNewComplete?.();
    },
  });

  const isLoading = refetching || isFetchingNew;

  // Track scroll position to show/hide header border
  const [isScrolled, setIsScrolled] = useState(false);
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolled(e.currentTarget.scrollTop > 0);
  }, []);

  const debugEnabled = process.env.NEXT_PUBLIC_DEBUG_SSE === "true";

  return (
    <div className="flex h-full flex-col bg-sidebar text-sidebar-foreground">
      {/* Header */}
      <SidebarHeader
        collapsed={collapsed}
        isLoading={isLoading}
        isScrolled={isScrolled}
        onCollapsedChange={(value) => onCollapsedChange?.(value)}
        onRefresh={handleRefresh}
        onFetchNew={handleFetchNew}
      />

      {/* Subscription list - hidden when collapsed */}
      {!collapsed && (
        <div className="flex-1 overflow-auto px-1 pb-2 overflow-x-hidden" onScroll={handleScroll}>
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <span className="text-sm text-muted-foreground">Loading...</span>
            </div>
          ) : (
            <div className="space-y-1">
              {/* Feeds section */}
              {/* Check if there are actual feeds (not just "all" entry) */}
              {subscriptions.filter((s) => s.id !== "all").length === 0 ? (
                <Empty className="py-6">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <Rss className="h-5 w-5" />
                    </EmptyMedia>
                    <EmptyTitle>No Feeds Yet</EmptyTitle>
                  </EmptyHeader>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigateToSettings("feeds")}
                  >
                    <Plus className="size-4" />
                    Feed
                  </Button>
                </Empty>
              ) : (
                <FeedsSection
                  subscriptions={subscriptions}
                  collapsed={collapsed}
                  selectedId={selectedId}
                  onSelect={onSelect}
                />
              )}

              {/* Reddit section (conditionally rendered) */}
              {isRedditEnabled() && (
                <RedditSection
                  collapsed={collapsed}
                  selectedId={selectedId}
                  onSelect={onSelect}
                />
              )}
            </div>
          )}
        </div>
      )}

      {/* Spacer when collapsed */}
      {collapsed && <div className="flex-1" />}

      {/* Footer navigation */}
      <div className="shrink-0 border-t">
        <div className="space-y-0.5">
          <button
            onClick={() => navigateToSettings()}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-4 pb-1 pt-2.5 text-sm hover:bg-accent select-none",
              viewMode === "settings" && "bg-accent font-medium",
              collapsed && "justify-center px-0"
            )}
          >
            <Settings className="size-4" />
            {!collapsed && (
              <span className="flex-1 truncate text-left">Settings</span>
            )}
          </button>
          {debugEnabled && !collapsed && (
            <div className="flex items-center gap-2 px-5 pt-2 pb-1 text-sm text-muted-foreground my-1 border-t">
              <SSEStatusIndicator />
            </div>
          )}
          <div className="my-1 border-t" />
          <UserMenu key="user-menu" collapsed={collapsed} />
        </div>
      </div>
    </div>
  );
}
