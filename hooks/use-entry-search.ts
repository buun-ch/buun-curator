/**
 * Hook for searching entries using Meilisearch.
 *
 * @module hooks/use-entry-search
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { type Entry } from "@/lib/types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

/** Search result entry with highlight information. */
export interface SearchResultEntry extends Entry {
  /** Highlighted title (with <mark> tags). */
  highlightedTitle?: string;
  /** Highlighted summary (with <mark> tags). */
  highlightedSummary?: string;
}

/** Search response from API. */
interface SearchResponse {
  entries: Array<{
    id: string;
    feedId: string;
    feedName?: string;
    title: string;
    summary: string | null;
    author: string | null;
    publishedAt: string | null;
    isRead: boolean;
    isStarred: boolean;
    createdAt: string;
    _highlighted?: {
      title?: string;
      summary?: string;
    };
  }>;
  totalCount: number;
  processingTimeMs: number;
  query: string;
}

/** Options for the useEntrySearch hook. */
interface UseEntrySearchOptions {
  /** The subscription ID to search within (feed-*, category-*, or "all"). */
  selectedSubscription: string;
  /** Search query string. */
  query: string;
  /** Debounce delay in ms (default: 300). */
  debounceMs?: number;
}

/** Return value from the useEntrySearch hook. */
interface UseEntrySearchReturn {
  /** Search results. */
  results: SearchResultEntry[];
  /** True during search. */
  loading: boolean;
  /** Total number of matches. */
  totalCount: number;
  /** Search processing time in ms. */
  processingTimeMs: number;
  /** True if search is enabled (query is not empty). */
  isSearching: boolean;
  /** The actual query being searched (debounced). */
  debouncedQuery: string;
}

/**
 * Fetches search results from the API.
 */
async function fetchSearchResults(
  query: string,
  selectedSubscription: string
): Promise<SearchResponse> {
  const params = new URLSearchParams();
  params.set("q", query);

  if (selectedSubscription.startsWith("feed-")) {
    params.set("feedId", selectedSubscription.replace("feed-", ""));
  } else if (selectedSubscription.startsWith("category-")) {
    params.set("categoryId", selectedSubscription.replace("category-", ""));
  }

  const response = await fetch(`/api/search?${params}`);
  if (!response.ok) {
    throw new Error("Search failed");
  }
  return response.json();
}

/**
 * Hook for searching entries.
 *
 * Uses Meilisearch for full-text search with debouncing.
 *
 * @param options - Hook options
 * @returns Search results and state
 */
export function useEntrySearch({
  selectedSubscription,
  query,
  debounceMs = 300,
}: UseEntrySearchOptions): UseEntrySearchReturn {
  const debouncedQuery = useDebouncedValue(query, debounceMs);
  const isSearching = debouncedQuery.trim().length > 0;

  const { data, isLoading } = useQuery({
    queryKey: ["search", debouncedQuery, selectedSubscription],
    queryFn: () => fetchSearchResults(debouncedQuery, selectedSubscription),
    enabled: isSearching,
    staleTime: 30000, // Cache results for 30 seconds
  });

  const results: SearchResultEntry[] =
    data?.entries.map((entry) => ({
      id: entry.id,
      feedId: entry.feedId,
      feedName: entry.feedName ?? null,
      title: entry.title,
      url: "", // Search results don't include URL
      summary: entry.summary ?? "",
      author: entry.author,
      publishedAt: entry.publishedAt,
      isRead: entry.isRead,
      isStarred: entry.isStarred,
      keep: false,
      labels: [],
      metadata: null,
      createdAt: entry.createdAt,
      highlightedTitle: entry._highlighted?.title,
      highlightedSummary: entry._highlighted?.summary,
    })) ?? [];

  return {
    results,
    loading: isLoading && isSearching,
    totalCount: data?.totalCount ?? 0,
    processingTimeMs: data?.processingTimeMs ?? 0,
    isSearching,
    debouncedQuery,
  };
}
