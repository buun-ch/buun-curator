"use client";

/**
 * Shared reader page component used by all feed routes.
 *
 * This component renders the full reader layout using URL state
 * from the context instead of Zustand for navigation-related state.
 *
 * @module app/(reader)/reader-page
 */

import "@copilotkit/react-ui/styles.css";

import { CopilotKit } from "@copilotkit/react-core";
import { useQueryClient } from "@tanstack/react-query";
import * as React from "react";
import { Toaster } from "sonner";
import { ulid } from "ulid";

import {
  AssistantSidebar,
  type ChatMode,
} from "@/components/reader/assistant-sidebar";
import { ContextPanel } from "@/components/reader/context-panel";
import { MobileLayout } from "@/components/reader/mobile-layout";
import { ReaderContent } from "@/components/reader/reader-content";
import { SubscriptionSidebar } from "@/components/reader/subscription-sidebar";
import { SettingsContent } from "@/components/settings/settings-content";
import { FixedWidthPanel } from "@/components/ui/fixed-width-panel";
import { useHydrated } from "@/hooks/use-hydrated";
import { useLayoutMode } from "@/hooks/use-layout-mode";
import { PreserveEntriesProvider } from "@/lib/preserve-entries-context";
import type { ContentPanelMode, ViewMode } from "@/lib/types";
import { useUrlState } from "@/lib/url-state-context";
import { useSettingsStore } from "@/stores/settings-store";

/** Minimum panel width in pixels when collapsed. */
const COLLAPSED_WIDTH = 48;

/** Props for ReaderPage component. */
interface ReaderPageProps {
  /** Initial view mode (reader or settings). */
  viewMode?: ViewMode;
}

export function ReaderPage({
  viewMode: initialViewMode = "reader",
}: ReaderPageProps) {
  const hydrated = useHydrated();
  const layoutMode = useLayoutMode();

  // URL state for navigation
  const {
    selectedSubscription: _selectedSubscription,
    entryId,
    section,
    subreddit,
  } = useUrlState();

  // View mode (settings is now a separate route, but we keep it for backward compatibility)
  const [viewMode, _setViewMode] = React.useState<ViewMode>(initialViewMode);

  // Subscription collapse state
  const [subscriptionCollapsed, setSubscriptionCollapsed] =
    React.useState(false);
  const handleSubscriptionCollapsedChange = React.useCallback(
    (collapsed: boolean) => {
      setSubscriptionCollapsed(collapsed);
    },
    [],
  );

  // Assistant state from Zustand (UI preference, kept in store)
  const assistantOpenRaw = useSettingsStore((state) => state.assistantOpen);
  const setAssistantOpen = useSettingsStore((state) => state.setAssistantOpen);
  const assistantOpen = hydrated ? assistantOpenRaw : false;

  // Panel sizes from store
  const subscriptionPanelWidth = useSettingsStore(
    (state) => state.subscriptionPanelWidth,
  );
  const setSubscriptionPanelWidth = useSettingsStore(
    (state) => state.setSubscriptionPanelWidth,
  );
  const assistantPanelWidth = useSettingsStore(
    (state) => state.assistantPanelWidth,
  );
  const setAssistantPanelWidth = useSettingsStore(
    (state) => state.setAssistantPanelWidth,
  );

  // Content panel mode (derived from URL section and selection)
  const [contentPanelMode, setContentPanelMode] =
    React.useState<ContentPanelMode>(() => {
      if (section === "reddit") {
        if (subreddit) return "subreddit-info";
        return "reddit-search";
      }
      return "entries";
    });

  // Update content panel mode when section changes
  React.useEffect(() => {
    if (section === "reddit") {
      if (subreddit) {
        setContentPanelMode("subreddit-info");
      } else {
        setContentPanelMode("reddit-search");
      }
    } else if (section === "feeds") {
      setContentPanelMode("entries");
    }
  }, [section, subreddit]);

  // Track current entry ID for AI context
  const [currentEntryId, setCurrentEntryId] = React.useState<
    string | undefined
  >(entryId);

  // Update currentEntryId when URL entryId changes
  React.useEffect(() => {
    if (entryId) {
      setCurrentEntryId(entryId);
    }
  }, [entryId]);

  // Chat mode for AI assistant
  const [chatMode, setChatMode] = React.useState<ChatMode>("dialogue");

  // Session ID for Langfuse tracing
  const [sessionId, setSessionId] = React.useState(() => `session-${ulid()}`);

  const handleNewSession = React.useCallback(() => {
    setSessionId(`session-${ulid()}`);
  }, []);

  // Context panel state
  const [contextPanelOpen, setContextPanelOpen] = React.useState(false);

  // Query client for cache invalidation
  const queryClient = useQueryClient();

  const handleFetchNewComplete = React.useCallback(async () => {
    // Invalidate all entries caches to trigger refetch
    await queryClient.invalidateQueries({ queryKey: ["entries"] });
  }, [queryClient]);

  // Effective width for subscription panel
  const effectiveSubscriptionWidth = subscriptionCollapsed
    ? COLLAPSED_WIDTH
    : subscriptionPanelWidth;

  // Determine effective view mode
  const effectiveViewMode =
    initialViewMode === "settings" ? "settings" : viewMode;

  // Effective layout mode (null during SSR/initial render -> desktop)
  const effectiveLayoutMode = layoutMode ?? "desktop";

  // Mobile layout for mobile mode (both reader and settings)
  const showMobileLayout = effectiveLayoutMode === "mobile";

  return (
    <PreserveEntriesProvider>
      <CopilotKit
        runtimeUrl="/api/copilotkit"
        properties={{ entryId: currentEntryId, mode: chatMode, sessionId }}
      >
        {showMobileLayout ? (
          /* Mobile Layout */
          <div className="relative h-dvh w-full">
            <MobileLayout onEntryChange={setCurrentEntryId} />
            <Toaster position="bottom-center" richColors closeButton />
          </div>
        ) : (
          /* Desktop / Compact Layout */
          <div className="flex h-dvh w-full">
            {/* Left Sidebar - Subscriptions */}
            <FixedWidthPanel
              width={effectiveSubscriptionWidth}
              onWidthChange={(width) => {
                if (!subscriptionCollapsed) {
                  setSubscriptionPanelWidth(width);
                }
              }}
              minWidth={COLLAPSED_WIDTH}
              maxWidth={400}
              className="h-full"
            >
              <SubscriptionSidebar
                key="subscription-sidebar"
                collapsed={subscriptionCollapsed}
                onCollapsedChange={handleSubscriptionCollapsedChange}
                viewMode={effectiveViewMode}
                onFetchNewComplete={handleFetchNewComplete}
              />
            </FixedWidthPanel>

            {/* Main content area */}
            <div className="toast-container relative flex min-w-0 flex-1 flex-col">
              <div className="flex min-h-0 flex-1">
                {effectiveViewMode === "reader" ? (
                  <ReaderContent
                    contentPanelMode={contentPanelMode}
                    setContentPanelMode={setContentPanelMode}
                    onEntryChange={setCurrentEntryId}
                    contextPanelOpen={contextPanelOpen}
                    onContextPanelOpenChange={setContextPanelOpen}
                  />
                ) : (
                  <SettingsContent />
                )}
              </div>

              {/* Context Panel */}
              {effectiveViewMode === "reader" && (
                <ContextPanel
                  open={contextPanelOpen}
                  onOpenChange={setContextPanelOpen}
                  entryId={currentEntryId}
                />
              )}

              {/* Toaster positioned relative to main content area */}
              <Toaster position="bottom-right" richColors closeButton />
            </div>

            {/* AI Assistant Sidebar */}
            {assistantOpen && (
              <FixedWidthPanel
                width={assistantPanelWidth}
                onWidthChange={setAssistantPanelWidth}
                minWidth={200}
                maxWidth={600}
                handlePosition="left"
                className="h-full"
              >
                <AssistantSidebar
                  open={assistantOpen}
                  onOpenChange={setAssistantOpen}
                  mode={chatMode}
                  onModeChange={setChatMode}
                  onNewSession={handleNewSession}
                />
              </FixedWidthPanel>
            )}

            {/* Collapsed Assistant Toggle */}
            {!assistantOpen && (
              <AssistantSidebar
                open={false}
                onOpenChange={setAssistantOpen}
                mode={chatMode}
                onModeChange={setChatMode}
                onNewSession={handleNewSession}
              />
            )}
          </div>
        )}
      </CopilotKit>
    </PreserveEntriesProvider>
  );
}
