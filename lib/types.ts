/**
 * Shared types and transform functions for frontend and API.
 *
 * This module defines the core domain types used throughout the application,
 * including feeds, entries, and Reddit content types.
 *
 * @module lib/types
 */

/** YouTube URL patterns for video ID extraction. */
const YOUTUBE_PATTERNS = [
  /(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([a-zA-Z0-9_-]{11})/,
  /(?:https?:\/\/)?youtu\.be\/([a-zA-Z0-9_-]{11})/,
  /(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([a-zA-Z0-9_-]{11})/,
  /(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/,
];

/**
 * Extracts YouTube video ID from various YouTube URL formats.
 *
 * @param url - URL to extract video ID from
 * @returns The 11-character video ID or undefined if not a YouTube URL
 */
function extractYoutubeVideoId(url: string): string | undefined {
  for (const pattern of YOUTUBE_PATTERNS) {
    const match = url.match(pattern);
    if (match) {
      return match[1];
    }
  }
  return undefined;
}

/** View modes for the main application layout. */
export type ViewMode = "reader" | "settings";

/** Filter modes for the entry list. */
export type FilterMode = "unread" | "all" | "starred" | "search";

/** Short URL values for FilterMode. */
export type FilterModeUrl = "u" | "a" | "s" | "q";

/** Mapping from FilterMode to short URL value. */
export const FILTER_MODE_TO_URL: Record<FilterMode, FilterModeUrl> = {
  unread: "u",
  all: "a",
  starred: "s",
  search: "q",
} as const;

/** Mapping from short URL value to FilterMode. */
export const URL_TO_FILTER_MODE: Record<FilterModeUrl, FilterMode> = {
  u: "unread",
  a: "all",
  s: "starred",
  q: "search",
} as const;

/** Sort modes for the entry list. */
export type SortMode = "newest" | "oldest" | "recommended";

/** Short URL values for SortMode. */
export type SortModeUrl = "n" | "o" | "r";

/** Mapping from SortMode to short URL value. */
export const SORT_MODE_TO_URL: Record<SortMode, SortModeUrl> = {
  newest: "n",
  oldest: "o",
  recommended: "r",
} as const;

/** Mapping from short URL value to SortMode. */
export const URL_TO_SORT_MODE: Record<SortModeUrl, SortMode> = {
  n: "newest",
  o: "oldest",
  r: "recommended",
} as const;

/**
 * Parses URL filter parameter to FilterMode.
 *
 * @param value - URL parameter value (short or full format)
 * @returns FilterMode or undefined if invalid
 */
export function parseFilterMode(value: string | null): FilterMode | undefined {
  if (!value) return undefined;
  // Support short URL values
  if (value in URL_TO_FILTER_MODE) {
    return URL_TO_FILTER_MODE[value as FilterModeUrl];
  }
  // Support full values for backward compatibility
  if (["unread", "all", "starred", "search"].includes(value)) {
    return value as FilterMode;
  }
  return undefined;
}

/**
 * Parses URL sort parameter to SortMode.
 *
 * @param value - URL parameter value (short or full format)
 * @returns SortMode or undefined if invalid
 */
export function parseSortMode(value: string | null): SortMode | undefined {
  if (!value) return undefined;
  // Support short URL values
  if (value in URL_TO_SORT_MODE) {
    return URL_TO_SORT_MODE[value as SortModeUrl];
  }
  // Support full values for backward compatibility
  if (["newest", "oldest", "recommended"].includes(value)) {
    return value as SortMode;
  }
  return undefined;
}

/** Language display modes for the content viewer. */
export type LanguageMode = "original" | "translated" | "both";

/** Filter modes for Reddit posts. */
export type RedditFilterMode = "starred" | "unread" | "all";

/** Label for categorizing entries. */
export interface Label {
  id: string;
  name: string;
  color: string;
}

/** Filter settings for Reddit post display. */
export interface RedditPostFilter {
  /** Minimum score threshold for displaying posts. */
  minScore: number;
  /** Filter mode for read/starred status. */
  mode: RedditFilterMode;
}

/** Content panel modes (determines what the middle panel displays). */
export type ContentPanelMode = "entries" | "reddit-search" | "subreddit-info";

/** Reddit post summary for list display. */
export interface RedditPost {
  id: string;
  title: string;
  subreddit: string;
  author: string;
  score: number;
  numComments: number;
  createdAt: Date;
  url: string;
  permalink: string;
  selftext?: string;
  thumbnail?: string;
  isNsfw: boolean;
}

/** Reddit post with full content and metadata for detail view. */
export interface RedditPostDetail extends RedditPost {
  subredditPrefixed: string;
  upvoteRatio: number;
  selftextHtml?: string;
  previewUrl?: string;
  isVideo: boolean;
  videoUrl?: string;
  flair?: string;
  domain: string;
  isSelf: boolean;
}

/** Reddit comment with nested replies. */
export interface RedditComment {
  id: string;
  author: string;
  body: string;
  bodyHtml?: string;
  score: number;
  createdAt: Date;
  depth: number;
  isSubmitter: boolean;
  stickied: boolean;
  replies: RedditComment[];
}

/** Subreddit metadata and statistics. */
export interface SubredditInfo {
  name: string;
  displayName: string;
  title: string;
  description: string;
  subscribers: number;
  activeUsers?: number;
  createdAt: Date;
  isNsfw: boolean;
  iconUrl?: string;
  bannerUrl?: string;
}

/** Feed category for organizing subscriptions. */
export interface Category {
  id: string;
  name: string;
}

/** RSS/Atom feed subscription. */
export interface Feed {
  id: string;
  name: string;
  url: string;
  siteUrl: string | null;
  categoryId: string | null;
  type: string | null;
}

/** Entry list item for Content List display (lightweight, no content/labels). */
export interface EntryListItem {
  id: string;
  feedId: string;
  feedName: string | null;
  title: string;
  url: string;
  summary: string;
  author: string | null;
  publishedAt: string | null;
  isRead: boolean;
  isStarred: boolean;
  keep: boolean;
  metadata: Record<string, unknown> | null;
  createdAt: string;
  thumbnailUrl?: string | null;
  // Computed field (populated by normalizeEntryListItem)
  youtubeVideoId?: string;
  // Recommendation score (cosine distance, lower = more similar)
  similarityScore?: number;
}

/** Full feed entry for Content Viewer (includes content and labels). */
export interface Entry extends EntryListItem {
  feedSiteUrl?: string | null;
  feedContent?: string;
  fullContent?: string;
  filteredContent?: string;
  translatedContent?: string;
  labels: Label[];
  updatedAt?: string;
}

/** Related entry with similarity score for display in related entries section. */
export interface RelatedEntry {
  id: string;
  feedId: string;
  feedName: string | null;
  title: string;
  url: string;
  summary: string;
  thumbnailUrl?: string | null;
  publishedAt: string | null;
  similarityScore: number;
}

/** Subscription item for the sidebar navigation tree. */
export interface Subscription {
  id: string;
  title: string;
  type: "category" | "feed" | "special";
  icon?: string;
  unreadCount?: number;
  children?: Subscription[];
}

/** Paginated entries response using cursor-based pagination. */
export interface EntriesConnection {
  edges: Array<{ node: EntryListItem; cursor: string }>;
  pageInfo: {
    hasNextPage: boolean;
    hasPreviousPage: boolean;
    startCursor: string | null;
    endCursor: string | null;
  };
  totalCount: number;
}

/**
 * Normalizes an EntryListItem by populating computed fields.
 *
 * Extracts youtubeVideoId from metadata or URL.
 *
 * @param entry - The entry list item from the database
 * @returns EntryListItem with computed fields (youtubeVideoId)
 */
export function normalizeEntryListItem(entry: EntryListItem): EntryListItem {
  const metadata = entry.metadata as {
    youtubeVideoId?: string;
  } | null;

  return {
    ...entry,
    youtubeVideoId: metadata?.youtubeVideoId || extractYoutubeVideoId(entry.url),
  };
}

/**
 * Normalizes an Entry by populating computed fields.
 *
 * Extracts youtubeVideoId from metadata or URL.
 *
 * @param entry - The full entry from the database
 * @returns Entry with computed fields (youtubeVideoId)
 */
export function normalizeEntry(entry: Entry): Entry {
  const metadata = entry.metadata as {
    youtubeVideoId?: string;
  } | null;

  return {
    ...entry,
    youtubeVideoId: metadata?.youtubeVideoId || extractYoutubeVideoId(entry.url),
  };
}
