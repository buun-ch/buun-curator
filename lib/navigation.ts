/**
 * Navigation helper functions for URL-based routing.
 *
 * Provides type-safe navigation functions that construct URLs
 * for feeds, entries, and Reddit sections.
 *
 * @module lib/navigation
 */

import {
  FILTER_MODE_TO_URL,
  type FilterMode,
  parseFilterMode,
  parseSortMode,
  SORT_MODE_TO_URL,
  type SortMode,
} from "./types";

/** Options for navigation that can include filter and sort parameters. */
export interface NavigationOptions {
  /** Filter mode. Defaults to 'unread' if not specified. */
  filter?: FilterMode;
  /** Sort mode. Defaults to 'newest' if not specified. */
  sort?: SortMode;
  /** Search query (used when filter is 'search'). */
  query?: string;
}

/**
 * Builds query string from navigation options.
 *
 * Only includes non-default values to keep URLs clean.
 *
 * @param options - Navigation options
 * @returns Query string starting with '?' or empty string
 */
function buildQueryString(options: NavigationOptions): string {
  const params = new URLSearchParams();

  if (options.filter && options.filter !== "unread") {
    params.set("f", FILTER_MODE_TO_URL[options.filter]);
  }
  if (options.sort && options.sort !== "newest") {
    params.set("s", SORT_MODE_TO_URL[options.sort]);
  }
  if (options.query) {
    params.set("q", options.query);
  }

  const queryString = params.toString();
  return queryString ? `?${queryString}` : "";
}

/**
 * Generates URL for all entries view.
 *
 * @param options - Optional filter/sort options
 * @returns URL path with query parameters
 */
export function allEntriesUrl(options: NavigationOptions = {}): string {
  return `/feeds${buildQueryString(options)}`;
}

/**
 * Generates URL for category view.
 *
 * @param categoryId - The category ID
 * @param options - Optional filter/sort options
 * @returns URL path with query parameters
 */
export function categoryUrl(
  categoryId: string,
  options: NavigationOptions = {},
): string {
  return `/feeds/c/${categoryId}${buildQueryString(options)}`;
}

/**
 * Generates URL for feed view.
 *
 * @param feedId - The feed ID
 * @param options - Optional filter/sort options
 * @returns URL path with query parameters
 */
export function feedUrl(
  feedId: string,
  options: NavigationOptions = {},
): string {
  return `/feeds/f/${feedId}${buildQueryString(options)}`;
}

/**
 * Generates URL for entry detail view.
 *
 * @param entryId - The entry ID
 * @param context - Optional context (category or feed) to maintain navigation state
 * @param options - Optional filter/sort options
 * @returns URL path with query parameters
 */
export function entryUrl(
  entryId: string,
  context?:
    | { type: "category"; categoryId: string }
    | { type: "feed"; feedId: string },
  options: NavigationOptions = {},
): string {
  const query = buildQueryString(options);

  if (!context) {
    return `/feeds/e/${entryId}${query}`;
  }

  if (context.type === "category") {
    return `/feeds/c/${context.categoryId}/e/${entryId}${query}`;
  }

  return `/feeds/f/${context.feedId}/e/${entryId}${query}`;
}

/**
 * Generates short URL for entry (direct link).
 *
 * @param entryId - The entry ID
 * @returns Short URL path
 */
export function entryShortUrl(entryId: string): string {
  return `/e/${entryId}`;
}

/**
 * Generates URL for Reddit home.
 *
 * @returns URL path
 */
export function redditHomeUrl(): string {
  return "/reddit";
}

/**
 * Generates URL for Reddit search.
 *
 * @param query - Optional search query
 * @returns URL path with query parameter
 */
export function redditSearchUrl(query?: string): string {
  if (query) {
    return `/reddit/search?q=${encodeURIComponent(query)}`;
  }
  return "/reddit/search";
}

/**
 * Generates URL for Reddit favorites.
 *
 * @returns URL path
 */
export function redditFavoritesUrl(): string {
  return "/reddit/favorites";
}

/**
 * Generates URL for subreddit view.
 *
 * @param subreddit - The subreddit name (without r/ prefix)
 * @returns URL path
 */
export function subredditUrl(subreddit: string): string {
  return `/reddit/r/${subreddit}`;
}

/** Valid settings category identifiers. */
export type SettingsCategory = "categories" | "feeds" | "labels" | "language";

/** Default settings category when none specified. */
export const DEFAULT_SETTINGS_CATEGORY: SettingsCategory = "categories";

/**
 * Generates URL for settings page.
 *
 * @param category - Optional settings category
 * @returns URL path
 */
export function settingsUrl(category?: SettingsCategory): string {
  if (category && category !== DEFAULT_SETTINGS_CATEGORY) {
    return `/settings/${category}`;
  }
  return "/settings";
}

/**
 * Parses settings category from URL pathname.
 *
 * @param pathname - Current pathname
 * @returns Settings category or default
 */
export function parseSettingsCategory(pathname: string): SettingsCategory {
  const match = pathname.match(/^\/settings\/([^/]+)/);
  const category = match?.[1];
  if (
    category === "categories" ||
    category === "feeds" ||
    category === "labels" ||
    category === "language"
  ) {
    return category;
  }
  return DEFAULT_SETTINGS_CATEGORY;
}

/**
 * Parses current URL to extract navigation state.
 *
 * @param pathname - Current pathname
 * @param searchParams - Current search params
 * @returns Parsed navigation state
 */
export function parseNavigationState(
  pathname: string,
  searchParams: URLSearchParams,
): {
  section: "feeds" | "reddit" | "settings";
  categoryId?: string;
  feedId?: string;
  entryId?: string;
  subreddit?: string;
  settingsCategory?: SettingsCategory;
  filter: FilterMode;
  sort: SortMode;
  query: string;
} {
  const filter = parseFilterMode(searchParams.get("f")) ?? "unread";
  const sort = parseSortMode(searchParams.get("s")) ?? "newest";
  const query = searchParams.get("q") || "";

  // Settings
  if (pathname.startsWith("/settings")) {
    return {
      section: "settings",
      settingsCategory: parseSettingsCategory(pathname),
      filter,
      sort,
      query,
    };
  }

  // Reddit routes
  if (pathname.startsWith("/reddit")) {
    const subredditMatch = pathname.match(/^\/reddit\/r\/([^/]+)/);
    return {
      section: "reddit",
      subreddit: subredditMatch?.[1],
      filter,
      sort,
      query,
    };
  }

  // Feeds routes
  const categoryMatch = pathname.match(/^\/feeds\/c\/([^/]+)/);
  const feedMatch = pathname.match(/^\/feeds\/f\/([^/]+)/);
  const entryMatch = pathname.match(/\/e\/([^/]+)$/);

  return {
    section: "feeds",
    categoryId: categoryMatch?.[1],
    feedId: feedMatch?.[1],
    entryId: entryMatch?.[1],
    filter,
    sort,
    query,
  };
}
