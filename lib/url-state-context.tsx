"use client";

/**
 * React Context for URL-based navigation state.
 *
 * Provides URL state to components without prop drilling.
 * State is derived from URL path and query parameters.
 *
 * @module lib/url-state-context
 */

import * as React from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import {
  type FilterMode,
  type SortMode,
  FILTER_MODE_TO_URL,
  SORT_MODE_TO_URL,
  parseFilterMode,
  parseSortMode,
} from "./types";
import {
  allEntriesUrl,
  categoryUrl,
  feedUrl,
  entryUrl,
  redditHomeUrl,
  redditSearchUrl,
  redditFavoritesUrl,
  subredditUrl,
  settingsUrl,
  parseSettingsCategory,
  type NavigationOptions,
  type SettingsCategory,
} from "./navigation";

/** URL state parsed from current location. */
export interface UrlStateValue {
  /** Current section. */
  section: "feeds" | "reddit" | "settings";
  /** Selected category ID (feeds section). */
  categoryId?: string;
  /** Selected feed ID (feeds section). */
  feedId?: string;
  /** Selected entry ID. */
  entryId?: string;
  /** Selected subreddit (reddit section). */
  subreddit?: string;
  /** Reddit sub-section. */
  redditSection?: "search" | "favorites";
  /** Settings category (settings section). */
  settingsCategory?: SettingsCategory;
  /** Filter mode. */
  filterMode: FilterMode;
  /** Sort mode. */
  sortMode: SortMode;
  /** Search query. */
  searchQuery: string;
  /** Legacy selectedSubscription format for backward compatibility. */
  selectedSubscription: string;
}

/** Navigation actions available in context. */
export interface UrlStateActions {
  /** Navigate to all entries. */
  navigateToAllEntries: (options?: NavigationOptions) => void;
  /** Navigate to category. */
  navigateToCategory: (categoryId: string, options?: NavigationOptions) => void;
  /** Navigate to feed. */
  navigateToFeed: (feedId: string, options?: NavigationOptions) => void;
  /** Navigate to entry. */
  navigateToEntry: (
    entryId: string,
    context?: { type: "category"; categoryId: string } | { type: "feed"; feedId: string },
    options?: NavigationOptions
  ) => void;
  /** Navigate to Reddit home. */
  navigateToRedditHome: () => void;
  /** Navigate to Reddit search. */
  navigateToRedditSearch: (query?: string) => void;
  /** Navigate to Reddit favorites. */
  navigateToRedditFavorites: () => void;
  /** Navigate to subreddit. */
  navigateToSubreddit: (subreddit: string) => void;
  /** Navigate to settings. */
  navigateToSettings: (category?: SettingsCategory) => void;
  /** Update filter mode (shallow navigation). */
  setFilterMode: (mode: FilterMode) => void;
  /** Update sort mode (shallow navigation). */
  setSortMode: (mode: SortMode) => void;
  /** Update search query (shallow navigation). */
  setSearchQuery: (query: string) => void;
}

/** Combined context value. */
export type UrlStateContextValue = UrlStateValue & UrlStateActions;

const UrlStateContext = React.createContext<UrlStateContextValue | null>(null);

/**
 * Parses URL pathname and search params into state.
 */
function parseUrlState(
  pathname: string,
  searchParams: URLSearchParams
): Omit<UrlStateValue, keyof UrlStateActions> {
  const filterMode = parseFilterMode(searchParams.get("f")) ?? "unread";
  const sortMode = parseSortMode(searchParams.get("s")) ?? "newest";
  const searchQuery = searchParams.get("q") || "";

  // Settings section
  if (pathname.startsWith("/settings")) {
    return {
      section: "settings",
      settingsCategory: parseSettingsCategory(pathname),
      filterMode,
      sortMode,
      searchQuery,
      selectedSubscription: "all",
    };
  }

  // Reddit section
  if (pathname.startsWith("/reddit")) {
    let redditSection: "search" | "favorites" | undefined;
    let subreddit: string | undefined;

    if (pathname.startsWith("/reddit/search")) {
      redditSection = "search";
    } else if (pathname.startsWith("/reddit/favorites")) {
      redditSection = "favorites";
    } else {
      const match = pathname.match(/^\/reddit\/r\/([^/]+)/);
      subreddit = match?.[1];
    }

    // Build legacy selectedSubscription
    let selectedSubscription = "reddit";
    if (redditSection === "search") {
      selectedSubscription = "reddit-search";
    } else if (redditSection === "favorites") {
      selectedSubscription = "reddit-favorites";
    } else if (subreddit) {
      selectedSubscription = `reddit-fav-${subreddit}`;
    }

    return {
      section: "reddit",
      redditSection,
      subreddit,
      filterMode,
      sortMode,
      searchQuery,
      selectedSubscription,
    };
  }

  // Feeds section (default)
  const categoryMatch = pathname.match(/^\/feeds\/c\/([^/]+)/);
  const feedMatch = pathname.match(/^\/feeds\/f\/([^/]+)/);
  const entryMatch = pathname.match(/\/e\/([^/]+)$/);

  const categoryId = categoryMatch?.[1];
  const feedId = feedMatch?.[1];
  const entryId = entryMatch?.[1];

  // Build legacy selectedSubscription
  let selectedSubscription = "all";
  if (feedId) {
    selectedSubscription = `feed-${feedId}`;
  } else if (categoryId) {
    selectedSubscription = `category-${categoryId}`;
  }

  return {
    section: "feeds",
    categoryId,
    feedId,
    entryId,
    filterMode,
    sortMode,
    searchQuery,
    selectedSubscription,
  };
}

/** Props for UrlStateProvider. */
interface UrlStateProviderProps {
  children: React.ReactNode;
}

/** Provider component for URL state context. */
export function UrlStateProvider({ children }: UrlStateProviderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Parse current URL state
  const urlState = React.useMemo(
    () => parseUrlState(pathname, searchParams),
    [pathname, searchParams]
  );

  // Build current query options from state
  const currentOptions = React.useMemo(
    (): NavigationOptions => ({
      filter: urlState.filterMode,
      sort: urlState.sortMode,
      query: urlState.searchQuery,
    }),
    [urlState.filterMode, urlState.sortMode, urlState.searchQuery]
  );

  // Navigation actions
  const navigateToAllEntries = React.useCallback(
    (options?: NavigationOptions) => {
      router.push(allEntriesUrl(options ?? currentOptions));
    },
    [router, currentOptions]
  );

  const navigateToCategory = React.useCallback(
    (categoryId: string, options?: NavigationOptions) => {
      router.push(categoryUrl(categoryId, options ?? currentOptions));
    },
    [router, currentOptions]
  );

  const navigateToFeed = React.useCallback(
    (feedId: string, options?: NavigationOptions) => {
      router.push(feedUrl(feedId, options ?? currentOptions));
    },
    [router, currentOptions]
  );

  const navigateToEntry = React.useCallback(
    (
      entryId: string,
      context?: { type: "category"; categoryId: string } | { type: "feed"; feedId: string },
      options?: NavigationOptions
    ) => {
      router.push(entryUrl(entryId, context, options ?? currentOptions));
    },
    [router, currentOptions]
  );

  const navigateToRedditHome = React.useCallback(() => {
    router.push(redditHomeUrl());
  }, [router]);

  const navigateToRedditSearch = React.useCallback(
    (query?: string) => {
      router.push(redditSearchUrl(query));
    },
    [router]
  );

  const navigateToRedditFavorites = React.useCallback(() => {
    router.push(redditFavoritesUrl());
  }, [router]);

  const navigateToSubreddit = React.useCallback(
    (subreddit: string) => {
      router.push(subredditUrl(subreddit));
    },
    [router]
  );

  const navigateToSettings = React.useCallback(
    (category?: SettingsCategory) => {
      router.push(settingsUrl(category));
    },
    [router]
  );

  // Shallow update actions (update query params without full navigation)
  const setFilterMode = React.useCallback(
    (mode: FilterMode) => {
      const params = new URLSearchParams(searchParams.toString());
      if (mode === "unread") {
        params.delete("f");
      } else {
        params.set("f", FILTER_MODE_TO_URL[mode]);
      }
      const query = params.toString();
      router.push(`${pathname}${query ? `?${query}` : ""}`, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  const setSortMode = React.useCallback(
    (mode: SortMode) => {
      const params = new URLSearchParams(searchParams.toString());
      if (mode === "newest") {
        params.delete("s");
      } else {
        params.set("s", SORT_MODE_TO_URL[mode]);
      }
      const query = params.toString();
      router.push(`${pathname}${query ? `?${query}` : ""}`, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  const setSearchQuery = React.useCallback(
    (query: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (query) {
        params.set("q", query);
        params.set("f", FILTER_MODE_TO_URL.search);
      } else {
        params.delete("q");
        // Check for both short and full values
        const currentFilter = params.get("f");
        if (currentFilter === "q" || currentFilter === "search") {
          params.delete("f");
        }
      }
      const queryStr = params.toString();
      router.push(`${pathname}${queryStr ? `?${queryStr}` : ""}`, { scroll: false });
    },
    [router, pathname, searchParams]
  );

  const contextValue = React.useMemo(
    (): UrlStateContextValue => ({
      ...urlState,
      navigateToAllEntries,
      navigateToCategory,
      navigateToFeed,
      navigateToEntry,
      navigateToRedditHome,
      navigateToRedditSearch,
      navigateToRedditFavorites,
      navigateToSubreddit,
      navigateToSettings,
      setFilterMode,
      setSortMode,
      setSearchQuery,
    }),
    [
      urlState,
      navigateToAllEntries,
      navigateToCategory,
      navigateToFeed,
      navigateToEntry,
      navigateToRedditHome,
      navigateToRedditSearch,
      navigateToRedditFavorites,
      navigateToSubreddit,
      navigateToSettings,
      setFilterMode,
      setSortMode,
      setSearchQuery,
    ]
  );

  return (
    <UrlStateContext.Provider value={contextValue}>
      {children}
    </UrlStateContext.Provider>
  );
}

/**
 * Hook to access URL state and navigation actions.
 *
 * @returns URL state and navigation actions
 * @throws Error if used outside UrlStateProvider
 */
export function useUrlState(): UrlStateContextValue {
  const context = React.useContext(UrlStateContext);
  if (!context) {
    throw new Error("useUrlState must be used within a UrlStateProvider");
  }
  return context;
}
