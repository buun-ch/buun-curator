import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { FilterMode, RedditFilterMode, SortMode } from "@/lib/types";

interface RedditSearch {
  id: string;
  title: string;
  query: string;
}

// Only filterMode is stored in localStorage (minScore is stored in DB)
interface SubredditLocalSettings {
  filterMode: RedditFilterMode;
}

interface SettingsState {
  // UI state (persisted across sessions)
  selectedSubscription: string;
  setSelectedSubscription: (id: string) => void;
  assistantOpen: boolean;
  setAssistantOpen: (open: boolean) => void;

  // Reddit state (shared across components)
  selectedSubredditName: string | undefined;
  setSelectedSubredditName: (name: string | undefined) => void;

  // Sidebar section collapse state
  feedsSectionOpen: boolean;
  setFeedsSectionOpen: (open: boolean) => void;
  redditSectionOpen: boolean;
  setRedditSectionOpen: (open: boolean) => void;
  // Category collapse state (keyed by category ID)
  categoryCollapseState: Record<string, boolean>;
  getCategoryOpen: (categoryId: string) => boolean;
  setCategoryOpen: (categoryId: string, open: boolean) => void;

  // Panel sizes (in pixels, for fixed-width panels)
  subscriptionPanelWidth: number;
  setSubscriptionPanelWidth: (width: number) => void;
  contentListPanelWidth: number;
  setContentListPanelWidth: (width: number) => void;
  assistantPanelWidth: number;
  setAssistantPanelWidth: (width: number) => void;
  translationPanelWidth: number;
  setTranslationPanelWidth: (width: number) => void;
  settingsNavPanelWidth: number;
  setSettingsNavPanelWidth: (width: number) => void;
  contextPanelHeight: number;
  setContextPanelHeight: (height: number) => void;

  // Feed settings
  feedFilterMode: FilterMode;
  setFeedFilterMode: (mode: FilterMode) => void;
  feedSortMode: SortMode;
  setFeedSortMode: (mode: SortMode) => void;

  // Reddit search queries
  redditSearches: RedditSearch[];
  addRedditSearch: (title: string, query: string) => void;
  removeRedditSearch: (id: string) => void;
  updateRedditSearch: (
    id: string,
    updates: Partial<Omit<RedditSearch, "id">>,
  ) => void;

  // Per-subreddit settings (keyed by subreddit name) - only filterMode in localStorage
  subredditSettings: Record<string, SubredditLocalSettings>;
  getSubredditFilterMode: (subredditName: string) => RedditFilterMode;
  setSubredditFilterMode: (
    subredditName: string,
    mode: RedditFilterMode,
  ) => void;
}

const DEFAULT_SUBREDDIT_FILTER_MODE: RedditFilterMode = "all";

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set, get) => ({
      // UI state (persisted across sessions)
      selectedSubscription: "all",
      setSelectedSubscription: (id) => set({ selectedSubscription: id }),
      assistantOpen: false,
      setAssistantOpen: (open) => set({ assistantOpen: open }),

      // Reddit state (shared across components)
      selectedSubredditName: undefined,
      setSelectedSubredditName: (name) => set({ selectedSubredditName: name }),

      // Sidebar section collapse state
      feedsSectionOpen: true,
      setFeedsSectionOpen: (open) => set({ feedsSectionOpen: open }),
      redditSectionOpen: true,
      setRedditSectionOpen: (open) => set({ redditSectionOpen: open }),
      // Category collapse state (keyed by category ID, defaults to open)
      categoryCollapseState: {},
      getCategoryOpen: (categoryId) => {
        const state = get().categoryCollapseState[categoryId];
        return state ?? true; // Default to open
      },
      setCategoryOpen: (categoryId, open) =>
        set((state) => ({
          categoryCollapseState: {
            ...state.categoryCollapseState,
            [categoryId]: open,
          },
        })),

      // Panel sizes (in pixels, for fixed-width panels)
      subscriptionPanelWidth: 250,
      setSubscriptionPanelWidth: (width) =>
        set({ subscriptionPanelWidth: width }),
      contentListPanelWidth: 320,
      setContentListPanelWidth: (width) =>
        set({ contentListPanelWidth: width }),
      assistantPanelWidth: 300,
      setAssistantPanelWidth: (width) => set({ assistantPanelWidth: width }),
      translationPanelWidth: 400,
      setTranslationPanelWidth: (width) =>
        set({ translationPanelWidth: width }),
      settingsNavPanelWidth: 250,
      setSettingsNavPanelWidth: (width) =>
        set({ settingsNavPanelWidth: width }),
      contextPanelHeight: 300,
      setContextPanelHeight: (height) => set({ contextPanelHeight: height }),

      // Feed settings
      feedFilterMode: "unread",
      setFeedFilterMode: (mode) => set({ feedFilterMode: mode }),
      feedSortMode: "newest",
      setFeedSortMode: (mode) => set({ feedSortMode: mode }),

      // Reddit search queries
      redditSearches: [],
      addRedditSearch: (title, query) =>
        set((state) => ({
          redditSearches: [
            ...state.redditSearches,
            { id: crypto.randomUUID(), title, query },
          ],
        })),
      removeRedditSearch: (id) =>
        set((state) => ({
          redditSearches: state.redditSearches.filter((s) => s.id !== id),
        })),
      updateRedditSearch: (id, updates) =>
        set((state) => ({
          redditSearches: state.redditSearches.map((s) =>
            s.id === id ? { ...s, ...updates } : s,
          ),
        })),

      // Per-subreddit settings (only filterMode - minScore is in DB)
      subredditSettings: {},
      getSubredditFilterMode: (subredditName) => {
        const settings = get().subredditSettings[subredditName];
        return settings?.filterMode ?? DEFAULT_SUBREDDIT_FILTER_MODE;
      },
      setSubredditFilterMode: (subredditName, mode) =>
        set((state) => ({
          subredditSettings: {
            ...state.subredditSettings,
            [subredditName]: {
              filterMode: mode,
            },
          },
        })),
    }),
    {
      name: "curator-settings",
      // Only persist these fields (exclude functions)
      // Note: selectedSubscription, feedFilterMode, feedSortMode are now URL-based
      partialize: (state) => ({
        assistantOpen: state.assistantOpen,
        feedsSectionOpen: state.feedsSectionOpen,
        redditSectionOpen: state.redditSectionOpen,
        categoryCollapseState: state.categoryCollapseState,
        subscriptionPanelWidth: state.subscriptionPanelWidth,
        contentListPanelWidth: state.contentListPanelWidth,
        assistantPanelWidth: state.assistantPanelWidth,
        translationPanelWidth: state.translationPanelWidth,
        settingsNavPanelWidth: state.settingsNavPanelWidth,
        contextPanelHeight: state.contextPanelHeight,
        redditSearches: state.redditSearches,
        subredditSettings: state.subredditSettings,
      }),
    },
  ),
);
