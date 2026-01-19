/**
 * URL state management using nuqs.
 *
 * Defines parsers and hooks for URL-based state management,
 * including filter mode, sort mode, and search query parameters.
 *
 * @module lib/url-state
 */

import {
  createSearchParamsCache,
  parseAsString,
  parseAsStringEnum,
} from "nuqs/server";

import type { FilterMode, SortMode } from "./types";

/** Filter mode options for URL parameter. */
export const filterModeOptions: FilterMode[] = [
  "unread",
  "all",
  "starred",
  "search",
];

/** Sort mode options for URL parameter. */
export const sortModeOptions: SortMode[] = ["newest", "oldest", "recommended"];

/** Parser for filter mode query parameter (?f=). */
export const filterParser =
  parseAsStringEnum(filterModeOptions).withDefault("unread");

/** Parser for sort mode query parameter (?s=). */
export const sortParser =
  parseAsStringEnum(sortModeOptions).withDefault("newest");

/** Parser for search query parameter (?q=). */
export const queryParser = parseAsString.withDefault("");

/** Search params cache for server components. */
export const searchParamsCache = createSearchParamsCache({
  f: filterParser,
  s: sortParser,
  q: queryParser,
});

/** Subscription selection type derived from URL path. */
export type SubscriptionSelection =
  | { type: "all" }
  | { type: "category"; categoryId: string }
  | { type: "feed"; feedId: string };

/** Reddit selection type derived from URL path. */
export type RedditSelection =
  | { type: "home" }
  | { type: "search" }
  | { type: "favorites" }
  | { type: "subreddit"; subreddit: string };

/** URL state parsed from path and query parameters. */
export interface UrlState {
  /** Current section (feeds or reddit). */
  section: "feeds" | "reddit";
  /** Subscription selection for feeds section. */
  subscription?: SubscriptionSelection;
  /** Reddit selection for reddit section. */
  reddit?: RedditSelection;
  /** Selected entry ID (if viewing entry detail). */
  entryId?: string;
  /** Filter mode. */
  filterMode: FilterMode;
  /** Sort mode. */
  sortMode: SortMode;
  /** Search query (when filterMode is 'search'). */
  searchQuery: string;
}

/**
 * Converts SubscriptionSelection to legacy selectedSubscription format.
 *
 * Used for backward compatibility with existing hooks and components
 * that expect the "all" | "feed-{id}" | "category-{id}" format.
 *
 * @param selection - The subscription selection from URL
 * @returns Legacy selectedSubscription string
 */
export function selectionToLegacyFormat(
  selection: SubscriptionSelection | undefined,
): string {
  if (!selection) return "all";
  switch (selection.type) {
    case "all":
      return "all";
    case "category":
      return `category-${selection.categoryId}`;
    case "feed":
      return `feed-${selection.feedId}`;
  }
}

/**
 * Converts legacy selectedSubscription format to SubscriptionSelection.
 *
 * @param legacyFormat - Legacy "all" | "feed-{id}" | "category-{id}" format
 * @returns SubscriptionSelection object
 */
export function legacyFormatToSelection(
  legacyFormat: string,
): SubscriptionSelection {
  if (legacyFormat === "all") {
    return { type: "all" };
  }
  if (legacyFormat.startsWith("feed-")) {
    return { type: "feed", feedId: legacyFormat.slice(5) };
  }
  if (legacyFormat.startsWith("category-")) {
    return { type: "category", categoryId: legacyFormat.slice(9) };
  }
  return { type: "all" };
}
