"use client";

/**
 * Mobile layout component with stack navigation.
 *
 * Provides full-screen push/pop navigation for mobile devices.
 * Views: Subscriptions -> List -> Viewer
 *
 * @module components/reader/mobile-layout
 */

import { useQueryClient } from "@tanstack/react-query";
import { AnimatePresence } from "framer-motion";
import * as React from "react";

import { useEntries } from "@/hooks/use-entries";
import { useUpdateEntry } from "@/hooks/use-entry";
import { useEntryActions } from "@/hooks/use-entry-actions";
import { useEntrySearch } from "@/hooks/use-entry-search";
import { useSelectedEntry } from "@/hooks/use-selected-entry";
import { useSelectedSubscriptionInfo } from "@/hooks/use-selected-subscription-info";
import { useSingleFeedIngestion } from "@/hooks/use-single-feed-ingestion";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { useTranslation } from "@/hooks/use-translation";
import { usePreserveEntries } from "@/lib/preserve-entries-context";
import type { EntryListItem, LanguageMode } from "@/lib/types";
import { useUrlState } from "@/lib/url-state-context";
import { type MobileView, useMobileNavStore } from "@/stores/mobile-nav-store";
import {
  selectIsEntryDistilled,
  selectIsEntryRefreshing,
  useWorkflowStore,
} from "@/stores/workflow-store";

import type { ContentViewerRef } from "./content-viewer";
import { MobileListView } from "./mobile/list-view";
import { MobileSettingsView } from "./mobile/settings-view";
import { MobileSubscriptionView } from "./mobile/subscription-view";
import { MobileViewerView } from "./mobile/viewer-view";

/** Props for MobileLayout. */
export interface MobileLayoutProps {
  onEntryChange?: (entryId: string | undefined) => void;
}

/**
 * Mobile layout with stack-based navigation.
 */
export function MobileLayout({ onEntryChange }: MobileLayoutProps) {
  const queryClient = useQueryClient();

  // Mobile navigation state
  const viewStack = useMobileNavStore((state) => state.viewStack);
  const direction = useMobileNavStore((state) => state.direction);
  const push = useMobileNavStore((state) => state.push);
  const pop = useMobileNavStore((state) => state.pop);
  const setStack = useMobileNavStore((state) => state.setStack);
  const currentView = viewStack[viewStack.length - 1];

  // URL state
  const {
    selectedSubscription,
    categoryId,
    feedId,
    section,
    filterMode: feedFilterMode,
    sortMode: feedSortMode,
    entryId: initialEntryId,
    setFilterMode: setFeedFilterMode,
    setSortMode: setFeedSortMode,
    navigateToAllEntries,
    navigateToCategory,
    navigateToFeed,
  } = useUrlState();

  // Local state for search
  const [searchQuery, setSearchQuery] = React.useState("");

  React.useEffect(() => {
    if (feedFilterMode !== "search") {
      setSearchQuery("");
    }
  }, [feedFilterMode]);

  // Subscriptions
  const {
    updateCountOnRead,
    updateCountOnToggleRead,
    refetch: refetchSubscriptions,
  } = useSubscriptions();

  const { info: subscriptionInfo } = useSelectedSubscriptionInfo();

  // Preserve entries
  const { preserveIds, addPreserveId, clearPreserveIds } = usePreserveEntries();

  React.useEffect(() => {
    clearPreserveIds();
  }, [feedFilterMode, selectedSubscription, clearPreserveIds]);

  // Entries
  const {
    entries,
    setEntries,
    loading: entriesLoading,
    hasMore: entriesHasMore,
    loadingMore: entriesLoadingMore,
    loadMore: handleLoadMoreEntries,
    refetch: refetchEntries,
    markAllAsRead,
    isMarkingAllAsRead,
  } = useEntries({ selectedSubscription, preserveIds });

  // Search
  const isSearchMode = feedFilterMode === "search";
  const {
    results: searchResults,
    loading: searchLoading,
    isSearching,
  } = useEntrySearch({
    selectedSubscription,
    query: isSearchMode ? searchQuery : "",
  });

  const displayEntries = React.useMemo(
    () => (isSearchMode ? (isSearching ? searchResults : []) : entries),
    [isSearchMode, isSearching, searchResults, entries],
  );
  const displayLoading = isSearchMode ? searchLoading : entriesLoading;

  // Feed ingestion
  const { isIngesting, handleIngest } = useSingleFeedIngestion({
    feedId: subscriptionInfo?.feedId,
    feedName: subscriptionInfo?.feedName,
    feedUrl: subscriptionInfo?.feedUrl,
    onComplete: async () => {
      await refetchSubscriptions();
      await refetchEntries();
    },
  });

  // Entry setter
  const setDisplayEntries = React.useCallback(
    (updater: typeof entries | ((prev: typeof entries) => typeof entries)) => {
      setEntries(updater);
    },
    [setEntries],
  );

  // Selected entry
  const {
    selectedEntry,
    setSelectedEntry,
    loading: entryLoading,
    selectEntry,
    hasPrevious,
    hasNext,
    goToPrevious,
    goToNext,
  } = useSelectedEntry({
    entries: displayEntries,
    setEntries: setDisplayEntries,
    onMarkAsRead: updateCountOnRead,
    onPreserveEntry: addPreserveId,
  });

  // Entry actions
  const { toggleStar, toggleKeep, toggleRead, refreshEntry } = useEntryActions({
    setEntries,
    onToggleRead: updateCountOnToggleRead,
    onMarkAsRead: addPreserveId,
  });

  // Entry update mutation
  const updateEntryMutation = useUpdateEntry();

  const handleUpdateAnnotation = React.useCallback(
    async (entryId: string, annotation: string) => {
      await updateEntryMutation.mutateAsync({ entryId, data: { annotation } });
    },
    [updateEntryMutation],
  );

  // Workflow state
  const isEntryRefreshingViaWorkflow = useWorkflowStore(
    selectIsEntryRefreshing(selectedEntry?.id),
  );
  const isEntryDistilled = useWorkflowStore(
    selectIsEntryDistilled(selectedEntry?.id),
  );
  const clearDistilledEntryId = useWorkflowStore(
    (state) => state.clearDistilledEntryId,
  );

  const wasRefreshingRef = React.useRef(false);

  const handleEntryUpdated = React.useCallback(
    async (entryId: string) => {
      await queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
      await queryClient.invalidateQueries({
        queryKey: ["entries"],
        refetchType: "none",
      });
    },
    [queryClient],
  );

  React.useEffect(() => {
    if (
      wasRefreshingRef.current &&
      !isEntryRefreshingViaWorkflow &&
      selectedEntry?.id
    ) {
      handleEntryUpdated(selectedEntry.id);
    }
    wasRefreshingRef.current = isEntryRefreshingViaWorkflow;
  }, [isEntryRefreshingViaWorkflow, selectedEntry?.id, handleEntryUpdated]);

  React.useEffect(() => {
    if (isEntryDistilled && selectedEntry?.id) {
      handleEntryUpdated(selectedEntry.id);
      clearDistilledEntryId(selectedEntry.id);
    }
  }, [
    isEntryDistilled,
    selectedEntry?.id,
    handleEntryUpdated,
    clearDistilledEntryId,
  ]);

  // Language mode
  const [languageMode, setLanguageMode] =
    React.useState<LanguageMode>("original");

  React.useEffect(() => {
    setLanguageMode("original");
  }, [selectedEntry?.id]);

  const hasTranslation = Boolean(
    selectedEntry?.translatedContent &&
    selectedEntry.translatedContent.length > 0,
  );

  // Translation
  const { isTranslating, triggerTranslation } = useTranslation({
    entryId: selectedEntry?.id,
    hasTranslation,
    languageMode,
    onTranslationComplete: handleEntryUpdated,
  });

  // Notify parent of entry changes
  React.useEffect(() => {
    onEntryChange?.(selectedEntry?.id);
  }, [selectedEntry?.id, onEntryChange]);

  // Content viewer ref
  const contentViewerRef = React.useRef<ContentViewerRef>(null);

  // Track if initial sync has been done
  const isInitializedRef = React.useRef(false);
  // Track previous URL state for detecting URL-driven navigation
  const prevUrlStateRef = React.useRef({
    feedId,
    categoryId,
    initialEntryId,
    section,
  });
  // Track if navigation is from internal UI (to skip useEffect stack rebuild)
  const isInternalNavigationRef = React.useRef(false);

  // Sync navigation stack with URL state (only on initial load or URL-driven navigation)
  React.useEffect(() => {
    // Skip if navigation was triggered from internal UI
    if (isInternalNavigationRef.current) {
      isInternalNavigationRef.current = false;
      prevUrlStateRef.current = { feedId, categoryId, initialEntryId, section };
      return;
    }

    const prevUrlState = prevUrlStateRef.current;
    const urlChanged =
      prevUrlState.feedId !== feedId ||
      prevUrlState.categoryId !== categoryId ||
      prevUrlState.initialEntryId !== initialEntryId ||
      prevUrlState.section !== section;

    // Update previous URL state
    prevUrlStateRef.current = { feedId, categoryId, initialEntryId, section };

    // Skip if already initialized and URL didn't change (user navigated via UI)
    if (isInitializedRef.current && !urlChanged) {
      return;
    }

    const newStack: MobileView[] = ["subscriptions"];

    // If settings section, show settings view
    if (section === "settings") {
      newStack.push("settings");
    } else {
      // If a specific feed or category is selected, show list
      // Note: "all" (no feedId/categoryId) stays on subscriptions unless explicitly navigated
      if (feedId || categoryId) {
        newStack.push("list");
      }

      // If an entry is selected, show viewer
      if (initialEntryId) {
        if (newStack[newStack.length - 1] !== "list") {
          newStack.push("list");
        }
        newStack.push("viewer");
      }
    }

    // Only update if different
    if (JSON.stringify(viewStack) !== JSON.stringify(newStack)) {
      setStack(newStack);
    }

    isInitializedRef.current = true;
  }, [feedId, categoryId, initialEntryId, section, viewStack, setStack]);

  // Handle entry selection from list
  const handleSelectEntry = React.useCallback(
    (entry: EntryListItem) => {
      isInternalNavigationRef.current = true;
      selectEntry(entry);
      push("viewer");
    },
    [selectEntry, push],
  );

  // Handle back navigation
  const handleBackFromList = React.useCallback(() => {
    // Mark as internal navigation to prevent useEffect from rebuilding stack
    isInternalNavigationRef.current = true;
    // Pop the stack to go back to subscriptions
    pop();
    // Navigate to /feeds (clears feedId/categoryId)
    navigateToAllEntries();
    setSelectedEntry(null);
  }, [pop, navigateToAllEntries, setSelectedEntry]);

  const handleBackFromViewer = React.useCallback(() => {
    // Mark as internal navigation to prevent useEffect from rebuilding stack
    isInternalNavigationRef.current = true;
    // Pop the stack to go back to list
    pop();
    // Clear selected entry
    setSelectedEntry(null);
    // Navigate back to list (URL may or may not change depending on context)
    if (feedId) {
      navigateToFeed(feedId);
    } else if (categoryId) {
      navigateToCategory(categoryId);
    } else {
      navigateToAllEntries();
    }
  }, [
    pop,
    feedId,
    categoryId,
    navigateToFeed,
    navigateToCategory,
    navigateToAllEntries,
    setSelectedEntry,
  ]);

  // Fetch new complete callback
  const handleFetchNewComplete = React.useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["entries"] });
  }, [queryClient]);

  // Handle subscription selection from sidebar
  const handleSubscriptionSelect = React.useCallback(
    (_id: string) => {
      // Mark as internal navigation to prevent useEffect from rebuilding stack
      isInternalNavigationRef.current = true;
      // Navigate to list view when any subscription is selected
      push("list");
    },
    [push],
  );

  // Handle settings click from sidebar
  const handleSettingsClick = React.useCallback(() => {
    // Mark as internal navigation to prevent useEffect from rebuilding stack
    isInternalNavigationRef.current = true;
    // Navigate to settings view
    push("settings");
  }, [push]);

  // Handle back from settings
  const handleBackFromSettings = React.useCallback(() => {
    // Mark as internal navigation to prevent useEffect from rebuilding stack
    isInternalNavigationRef.current = true;
    // Pop the stack to go back to subscriptions
    pop();
    // Navigate back to feeds
    navigateToAllEntries();
  }, [pop, navigateToAllEntries]);

  return (
    <div className="relative h-dvh w-full overflow-hidden bg-background">
      <AnimatePresence mode="popLayout" initial={false} custom={direction}>
        {currentView === "subscriptions" && (
          <MobileSubscriptionView
            key="subscriptions"
            onFetchNewComplete={handleFetchNewComplete}
            onSubscriptionSelect={handleSubscriptionSelect}
            onSettingsClick={handleSettingsClick}
          />
        )}

        {currentView === "list" && (
          <MobileListView
            key="list"
            onBack={handleBackFromList}
            entries={displayEntries}
            loading={displayLoading}
            filterMode={feedFilterMode}
            onFilterModeChange={setFeedFilterMode}
            sortMode={feedSortMode}
            onSortModeChange={setFeedSortMode}
            hasMore={isSearchMode ? false : entriesHasMore}
            loadingMore={entriesLoadingMore}
            onLoadMore={handleLoadMoreEntries}
            selectedId={selectedEntry?.id}
            onSelect={handleSelectEntry}
            onToggleStar={toggleStar}
            onRefetch={handleIngest}
            isRefetching={isIngesting}
            onMarkAllAsRead={markAllAsRead}
            isMarkingAllAsRead={isMarkingAllAsRead}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
          />
        )}

        {currentView === "viewer" && (
          <MobileViewerView
            key="viewer"
            viewerRef={contentViewerRef}
            onBack={handleBackFromViewer}
            entry={selectedEntry}
            loading={entryLoading}
            onToggleStar={toggleStar}
            onToggleKeep={toggleKeep}
            onToggleRead={toggleRead}
            onRefresh={refreshEntry}
            refreshing={isEntryRefreshingViaWorkflow}
            onPrevious={goToPrevious}
            onNext={goToNext}
            hasPrevious={hasPrevious}
            hasNext={hasNext}
            languageMode={languageMode}
            onLanguageModeChange={setLanguageMode}
            isTranslating={isTranslating}
            onRetranslate={triggerTranslation}
            onSelectEntry={(entry) => selectEntry(entry as EntryListItem)}
            onUpdateAnnotation={handleUpdateAnnotation}
          />
        )}

        {currentView === "settings" && (
          <MobileSettingsView key="settings" onBack={handleBackFromSettings} />
        )}
      </AnimatePresence>
    </div>
  );
}
