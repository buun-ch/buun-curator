"use client";

import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { FixedWidthPanel } from "@/components/ui/fixed-width-panel";
import { ContentList } from "@/components/reader/content-list";
import { ContentViewer, type ContentViewerRef } from "@/components/reader/content-viewer";
import { RedditSearchResults } from "@/components/reader/reddit-search-results";
import { SubredditInfo } from "@/components/reader/subreddit-info";
import { RedditPostViewer } from "@/components/reader/reddit-post-viewer";
import { TranslationPanel } from "@/components/reader/translation-panel";
import { KeyboardShortcutsDialog } from "@/components/reader/keyboard-shortcuts-dialog";
import { useEntries } from "@/hooks/use-entries";
import { useEntrySearch } from "@/hooks/use-entry-search";
import { useSelectedEntry } from "@/hooks/use-selected-entry";
import { useEntryActions } from "@/hooks/use-entry-actions";
import { useUpdateEntry } from "@/hooks/use-entry";
import { useRedditState } from "@/hooks/use-reddit-state";
import { useSubscriptions } from "@/hooks/use-subscriptions";
import { useSelectedSubscriptionInfo } from "@/hooks/use-selected-subscription-info";
import { useSingleFeedIngestion } from "@/hooks/use-single-feed-ingestion";
import { useTranslation } from "@/hooks/use-translation";
import { useSettingsStore } from "@/stores/settings-store";
import { useWorkflowStore, selectIsEntryRefreshing, selectIsEntryDistilled } from "@/stores/workflow-store";
import { useKeyboardShortcuts } from "@/hooks/use-keyboard-shortcuts";
import { isRedditEnabled } from "@/lib/config";
import { type ContentPanelMode, type Entry, type EntryListItem, type LanguageMode } from "@/lib/types";
import { useUrlState } from "@/lib/url-state-context";
import { usePreserveEntries } from "@/lib/preserve-entries-context";
import { createLogger } from "@/lib/logger";

const log = createLogger("components:reader-content");
/** Scroll amount in pixels for keyboard shortcuts. */
const SCROLL_AMOUNT = 200;

export interface ReaderContentProps {
  contentPanelMode: ContentPanelMode;
  setContentPanelMode: React.Dispatch<React.SetStateAction<ContentPanelMode>>;
  onEntryChange?: (entryId: string | undefined) => void;
  contextPanelOpen?: boolean;
  onContextPanelOpenChange?: (open: boolean) => void;
}

export function ReaderContent({
  contentPanelMode,
  setContentPanelMode,
  onEntryChange,
  contextPanelOpen,
  onContextPanelOpenChange,
}: ReaderContentProps) {
  // Query client for cache invalidation
  const queryClient = useQueryClient();

  // URL state (navigation-related state)
  const {
    selectedSubscription,
    categoryId,
    feedId,
    filterMode: feedFilterMode,
    sortMode: feedSortMode,
    entryId: initialEntryId,
    setFilterMode: setFeedFilterMode,
    setSortMode: setFeedSortMode,
    navigateToAllEntries,
  } = useUrlState();

  // Local state for search query (not persisted to URL to avoid IME issues)
  const [searchQuery, setSearchQuery] = React.useState("");

  // Clear search query when leaving search mode
  React.useEffect(() => {
    if (feedFilterMode !== "search") {
      setSearchQuery("");
    }
  }, [feedFilterMode]);

  // Settings from store (UI preferences only)
  const contentListPanelWidth = useSettingsStore(
    (state) => state.contentListPanelWidth
  );
  const setContentListPanelWidth = useSettingsStore(
    (state) => state.setContentListPanelWidth
  );
  const translationPanelWidth = useSettingsStore(
    (state) => state.translationPanelWidth
  );
  const setTranslationPanelWidth = useSettingsStore(
    (state) => state.setTranslationPanelWidth
  );

  // Subscriptions data (for updating unread counts)
  const { updateCountOnRead, updateCountOnToggleRead, refetch: refetchSubscriptions } =
    useSubscriptions();

  // Selected subscription info (title, type, feed details for refetch)
  const { info: subscriptionInfo } = useSelectedSubscriptionInfo();

  // Preserve entries context (for keeping read entries visible in unread mode)
  const { preserveIds, addPreserveId, clearPreserveIds } = usePreserveEntries();

  // Clear preserved IDs when filter mode or subscription changes
  React.useEffect(() => {
    log.debug({ filter: feedFilterMode, subscription: selectedSubscription }, "clearing preserveIds due to filter/subscription change");
    clearPreserveIds();
  }, [feedFilterMode, selectedSubscription, clearPreserveIds]);

  // Log preserveIds before useEntries
  // log.debug({ preserveIds: preserveIds ? Array.from(preserveIds) : [] }, "useEntries called with preserveIds");

  // Entries data
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

  // Search mode check
  const isSearchMode = feedFilterMode === "search";

  // Search results (only fetch when in search mode with query)
  const {
    results: searchResults,
    loading: searchLoading,
    isSearching,
  } = useEntrySearch({
    selectedSubscription,
    query: isSearchMode ? searchQuery : "",
  });

  // Display logic:
  // - Search mode with query: show search results
  // - Search mode without query: show empty list
  // - Other modes: show regular entries
  const displayEntries = React.useMemo(
    () => (isSearchMode ? (isSearching ? searchResults : []) : entries),
    [isSearchMode, isSearching, searchResults, entries]
  );
  const displayLoading = isSearchMode ? searchLoading : entriesLoading;

  // Single feed ingestion (for refetch button)
  const { isIngesting, handleIngest } = useSingleFeedIngestion({
    feedId: subscriptionInfo?.feedId,
    feedName: subscriptionInfo?.feedName,
    feedUrl: subscriptionInfo?.feedUrl,
    onComplete: async () => {
      await refetchSubscriptions();
      await refetchEntries();
    },
  });

  // Reddit state (only used when Reddit is enabled)
  const redditState = useRedditState({
    setContentPanelMode,
  });

  // Handle favorite removal - navigate back to entries
  const handleFavoriteRemoved = React.useCallback(() => {
    navigateToAllEntries();
    setContentPanelMode("entries");
  }, [navigateToAllEntries, setContentPanelMode]);

  // Setter for entries that works with both regular and search modes
  const setDisplayEntries = React.useCallback(
    (updater: typeof entries | ((prev: typeof entries) => typeof entries)) => {
      // Always update the main entries list (for read status sync)
      setEntries(updater);
    },
    [setEntries]
  );

  // Selected entry - use displayEntries for navigation
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

  // Build entry URL helper
  const buildEntryUrl = React.useCallback((entryId: string) => {
    let newPath: string;
    if (feedId) {
      newPath = `/feeds/f/${feedId}/e/${entryId}`;
    } else if (categoryId) {
      newPath = `/feeds/c/${categoryId}/e/${entryId}`;
    } else {
      newPath = `/feeds/e/${entryId}`;
    }
    return `${newPath}${window.location.search}`;
  }, [feedId, categoryId]);

  // Update URL when selected entry changes (using pushState to preserve history)
  const prevEntryIdRef = React.useRef<string | undefined>(initialEntryId);
  const isPopstateNavigation = React.useRef(false);

  React.useEffect(() => {
    if (selectedEntry?.id && selectedEntry.id !== prevEntryIdRef.current) {
      // Skip URL update if this change came from popstate (back/forward)
      if (isPopstateNavigation.current) {
        isPopstateNavigation.current = false;
        prevEntryIdRef.current = selectedEntry.id;
        return;
      }

      const newUrl = buildEntryUrl(selectedEntry.id);
      // Use pushState to add to history without triggering Next.js navigation
      window.history.pushState({ entryId: selectedEntry.id }, "", newUrl);
      prevEntryIdRef.current = selectedEntry.id;
    }
  }, [selectedEntry?.id, buildEntryUrl]);

  // Handle browser back/forward navigation
  React.useEffect(() => {
    const handlePopstate = () => {
      // Extract entry ID from current URL
      const match = window.location.pathname.match(/\/e\/([^/]+)$/);
      const urlEntryId = match?.[1];

      if (urlEntryId && urlEntryId !== selectedEntry?.id) {
        // Find the entry in the list and select it
        const entry = displayEntries.find(e => e.id === urlEntryId);
        isPopstateNavigation.current = true;
        if (entry) {
          selectEntry(entry);
        } else {
          // Entry not in list (e.g., from different feed via Related Entries)
          // Fetch from API using minimal entry object
          selectEntry({ id: urlEntryId } as Entry);
        }
      } else if (!urlEntryId && selectedEntry) {
        // URL has no entry - clear selection (user went back to list view)
        isPopstateNavigation.current = true;
        setSelectedEntry(null);
        prevEntryIdRef.current = undefined;
      }
    };

    window.addEventListener("popstate", handlePopstate);
    return () => window.removeEventListener("popstate", handlePopstate);
  }, [displayEntries, selectedEntry, selectEntry, setSelectedEntry]);

  // Load entry from URL on mount (when navigating directly to entry URL)
  const hasLoadedInitialEntry = React.useRef(false);
  React.useEffect(() => {
    if (initialEntryId && !hasLoadedInitialEntry.current && !selectedEntry) {
      hasLoadedInitialEntry.current = true;
      // Create a minimal entry object to trigger selection
      selectEntry({ id: initialEntryId } as Entry);
    }
  }, [initialEntryId, selectedEntry, selectEntry]);

  // Alias for clarity
  const handleSelectEntry = selectEntry;
  const handlePreviousEntry = goToPrevious;
  const handleNextEntry = goToNext;

  // Entry actions
  const { toggleStar, toggleKeep, toggleRead, refreshEntry } =
    useEntryActions({
      setEntries,
      onToggleRead: updateCountOnToggleRead,
      onMarkAsRead: addPreserveId,
    });

  // Entry update mutation for annotation
  const updateEntryMutation = useUpdateEntry();

  // Update annotation handler
  const handleUpdateAnnotation = React.useCallback(
    async (entryId: string, annotation: string) => {
      await updateEntryMutation.mutateAsync({ entryId, data: { annotation } });
    },
    [updateEntryMutation]
  );

  // Check if selected entry is being refreshed via workflow store
  const isEntryRefreshingViaWorkflow = useWorkflowStore(
    selectIsEntryRefreshing(selectedEntry?.id)
  );

  // Check if selected entry has been distilled (summary generated)
  const isEntryDistilled = useWorkflowStore(
    selectIsEntryDistilled(selectedEntry?.id)
  );
  const clearDistilledEntryId = useWorkflowStore((state) => state.clearDistilledEntryId);

  // Track previous refreshing state to detect completion
  const wasRefreshingRef = React.useRef(false);

  // Refetch entry by ID (called when translation or refresh completes)
  const handleEntryUpdated = React.useCallback(async (entryId: string) => {
    // Invalidate the entry query - TanStack Query will refetch
    await queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
    // Mark entries list as stale (for summary changes etc.)
    await queryClient.invalidateQueries({
      queryKey: ["entries"],
      refetchType: "none",
    });
  }, [queryClient]);

  // Refetch entry when refresh completes (was refreshing, now not)
  React.useEffect(() => {
    if (wasRefreshingRef.current && !isEntryRefreshingViaWorkflow && selectedEntry?.id) {
      handleEntryUpdated(selectedEntry.id);
    }
    wasRefreshingRef.current = isEntryRefreshingViaWorkflow;
  }, [isEntryRefreshingViaWorkflow, selectedEntry?.id, handleEntryUpdated]);

  // Refetch entry when distillation completes (summary generated)
  React.useEffect(() => {
    if (isEntryDistilled && selectedEntry?.id) {
      handleEntryUpdated(selectedEntry.id);
      clearDistilledEntryId(selectedEntry.id);
    }
  }, [isEntryDistilled, selectedEntry?.id, handleEntryUpdated, clearDistilledEntryId]);

  // Language mode state (resets when entry changes)
  const [languageMode, setLanguageMode] = React.useState<LanguageMode>("original");

  // Reset language mode when entry changes
  React.useEffect(() => {
    setLanguageMode("original");
  }, [selectedEntry?.id]);

  // Check if entry has translation
  const hasTranslation = Boolean(
    selectedEntry?.translatedContent && selectedEntry.translatedContent.length > 0
  );

  // Translation hook
  const { isTranslating, triggerTranslation } = useTranslation({
    entryId: selectedEntry?.id,
    hasTranslation,
    languageMode,
    onTranslationComplete: handleEntryUpdated,
  });

  // Notify parent of entry changes (for AI context)
  React.useEffect(() => {
    onEntryChange?.(selectedEntry?.id);
  }, [selectedEntry?.id, onEntryChange]);

  // Update document title based on selection
  React.useEffect(() => {
    const truncate = (text: string, maxLength: number = 30) =>
      text.length > maxLength ? text.slice(0, maxLength) + "…" : text;

    let title = "Buun Curator";

    if (selectedEntry) {
      // Entry selected: <Entry.title> | <Feed.name>
      const entryTitle = truncate(selectedEntry.title);
      const feedName = selectedEntry.feedName ? truncate(selectedEntry.feedName) : "";
      title = feedName ? `${entryTitle} | ${feedName}` : entryTitle;
    } else if (subscriptionInfo) {
      // Feed or Category selected
      if (subscriptionInfo.type === "feed") {
        title = truncate(subscriptionInfo.title);
      } else if (subscriptionInfo.type === "category") {
        title = `Category: ${truncate(subscriptionInfo.title)}`;
      }
      // "special" type (All Entries) keeps default title
    }

    document.title = title;
  }, [selectedEntry, subscriptionInfo]);

  // Content viewer ref for scroll control
  const contentViewerRef = React.useRef<ContentViewerRef>(null);

  // Keyboard shortcuts help dialog
  const [shortcutsDialogOpen, setShortcutsDialogOpen] = React.useState(false);

  // Keyboard shortcuts (only enabled in entries mode)
  useKeyboardShortcuts({
    onNextEntry: handleNextEntry,
    onPreviousEntry: handlePreviousEntry,
    onScrollDown: () => contentViewerRef.current?.scrollBy(SCROLL_AMOUNT),
    onScrollUp: () => contentViewerRef.current?.scrollBy(-SCROLL_AMOUNT),
    onScrollToTop: () => contentViewerRef.current?.scrollToTop(),
    onScrollToBottom: () => contentViewerRef.current?.scrollToBottom(),
    onOpenEntry: () => {
      if (selectedEntry?.url) {
        window.open(selectedEntry.url, "_blank");
      }
    },
    onToggleStar: () => {
      if (selectedEntry) {
        toggleStar(selectedEntry);
      }
    },
    onToggleRead: () => {
      if (selectedEntry) {
        toggleRead(selectedEntry);
      }
    },
    onToggleKeep: () => {
      if (selectedEntry) {
        toggleKeep(selectedEntry);
      }
    },
    onShowHelp: () => setShortcutsDialogOpen(true),
    enabled: contentPanelMode === "entries",
  });

  return (
    <>
      {/* Content List Panel - fixed width */}
      <FixedWidthPanel
        width={contentListPanelWidth}
        onWidthChange={setContentListPanelWidth}
        minWidth={200}
        maxWidth={600}
        className="h-full"
      >
        {contentPanelMode === "entries" && (
          <ContentList
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
            subscriptionInfo={subscriptionInfo}
            onRefetch={handleIngest}
            isRefetching={isIngesting}
            onMarkAllAsRead={markAllAsRead}
            isMarkingAllAsRead={isMarkingAllAsRead}
            searchQuery={searchQuery}
            onSearchQueryChange={setSearchQuery}
          />
        )}
        {isRedditEnabled() && contentPanelMode === "reddit-search" && (
          <RedditSearchResults
            posts={redditState.redditPosts}
            loading={redditState.redditLoading}
            searchQuery={redditState.redditSearchQuery}
            onSearch={redditState.handleRedditSearch}
            selectedId={redditState.selectedRedditPost?.id}
            onSelect={redditState.setSelectedRedditPost}
          />
        )}
        {isRedditEnabled() && contentPanelMode === "subreddit-info" && (
          <SubredditInfo
            subredditName={redditState.selectedSubredditName}
            favoriteId={redditState.currentFavoriteId ?? undefined}
            selectedPostId={redditState.selectedRedditPost?.id}
            onSelectPost={redditState.setSelectedRedditPost}
            onRemoved={handleFavoriteRemoved}
          />
        )}
      </FixedWidthPanel>

      {/* Content Viewer - fills remaining space */}
      <div className="flex min-w-0 flex-1 flex-col">
        {contentPanelMode === "entries" ? (
          <ContentViewer
            key={selectedEntry?.id}
            ref={contentViewerRef}
            entry={selectedEntry}
            loading={entryLoading}
            onToggleStar={toggleStar}
            onToggleKeep={toggleKeep}
            onToggleRead={toggleRead}
            onRefresh={refreshEntry}
            refreshing={isEntryRefreshingViaWorkflow}
            onPrevious={handlePreviousEntry}
            onNext={handleNextEntry}
            hasPrevious={hasPrevious}
            hasNext={hasNext}
            languageMode={languageMode}
            onLanguageModeChange={setLanguageMode}
            isTranslating={isTranslating}
            onRetranslate={triggerTranslation}
            contextPanelOpen={contextPanelOpen}
            onContextPanelOpenChange={onContextPanelOpenChange}
            onSelectEntry={(entry) => selectEntry(entry as EntryListItem)}
            onUpdateAnnotation={handleUpdateAnnotation}
          />
        ) : isRedditEnabled() ? (
          <RedditPostViewer
            post={redditState.redditPostData?.post}
            comments={redditState.redditPostData?.comments}
            loading={redditState.redditPostLoading}
          />
        ) : null}
      </div>

      {/* Translation Panel - shown in "both" mode */}
      {contentPanelMode === "entries" && languageMode === "both" && (
        <FixedWidthPanel
          width={translationPanelWidth}
          onWidthChange={setTranslationPanelWidth}
          minWidth={250}
          maxWidth={1200}
          handlePosition="left"
          className="h-full"
        >
          <TranslationPanel
            translatedContent={selectedEntry?.translatedContent}
            isTranslating={isTranslating}
            onRetranslate={triggerTranslation}
            onClose={() => setLanguageMode("original")}
          />
        </FixedWidthPanel>
      )}

      {/* Keyboard shortcuts help dialog */}
      <KeyboardShortcutsDialog
        open={shortcutsDialogOpen}
        onOpenChange={setShortcutsDialogOpen}
      />
    </>
  );
}
