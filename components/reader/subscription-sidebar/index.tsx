"use client";

import { Plus, Rss, Settings } from "lucide-react";
import * as React from "react";
import { useCallback, useState } from "react";

import { SSEStatusIndicator } from "@/components/status";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { useFeedIngestion } from "@/hooks/use-feed-ingestion";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { isDebugSSEEnabled, isRedditEnabled } from "@/lib/config";
import { usePreserveEntries } from "@/lib/preserve-entries-context";
import { useUrlState } from "@/lib/url-state-context";
import { cn } from "@/lib/utils";

import { FeedsSection } from "./feeds-section";
import { RedditSection } from "./reddit-section";
import { SidebarHeader } from "./sidebar-header";
import type { SubscriptionSidebarProps } from "./types";
import { UserMenu } from "./user-menu";

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
  onSubscriptionSelect,
  onSettingsClick,
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
      // Notify parent of selection (for mobile navigation)
      onSubscriptionSelect?.(id);
    },
    [
      navigateToAllEntries,
      navigateToCategory,
      navigateToFeed,
      navigateToRedditHome,
      navigateToRedditSearch,
      navigateToRedditFavorites,
      navigateToSubreddit,
      onSubscriptionSelect,
    ],
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

  const debugEnabled = isDebugSSEEnabled();

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
        <div
          className="flex-1 overflow-auto overflow-x-hidden px-0 pb-2"
          onScroll={handleScroll}
        >
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <span className="text-sm text-sidebar-foreground">
                Loading...
              </span>
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
            onClick={() => {
              navigateToSettings();
              onSettingsClick?.();
            }}
            className={cn(
              "flex w-full items-center gap-2 border-b px-4 py-2 text-sm select-none hover:bg-sidebar-accent",
              viewMode === "settings" && "bg-sidebar-accent font-medium",
              collapsed && "justify-center px-0",
            )}
          >
            <Settings className="size-4" />
            {!collapsed && (
              <span className="flex-1 truncate text-left">Settings</span>
            )}
          </button>
          {debugEnabled && !collapsed && (
            <div className="my-1 flex items-center gap-2 border-t px-5 pt-2 pb-1 text-sm text-sidebar-foreground">
              <SSEStatusIndicator />
            </div>
          )}
          <UserMenu key="user-menu" collapsed={collapsed} />
        </div>
      </div>
    </div>
  );
}
