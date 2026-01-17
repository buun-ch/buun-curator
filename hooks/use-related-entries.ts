/**
 * Hook for fetching related entries based on embedding similarity.
 *
 * Uses TanStack Query for caching. Results are cached for 5 minutes.
 *
 * @module hooks/use-related-entries
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import type { RelatedEntry } from "@/lib/types";

interface RelatedEntriesResponse {
  entries: RelatedEntry[];
}

/**
 * Fetches related entries for a given entry ID.
 *
 * @param entryId - Entry ID to find related entries for
 * @returns Promise resolving to array of related entries
 */
async function fetchRelatedEntries(entryId: string): Promise<RelatedEntry[]> {
  const response = await fetch(`/api/entries/${entryId}/related`);
  if (!response.ok) {
    throw new Error("Failed to fetch related entries");
  }
  const data: RelatedEntriesResponse = await response.json();
  return data.entries;
}

/**
 * Hook for fetching related entries based on embedding similarity.
 *
 * Uses vector similarity search to find entries with similar content.
 * Results are cached for 5 minutes since embeddings rarely change.
 *
 * @param entryId - Entry ID to find related entries for (undefined to skip)
 * @returns Query result with related entries array
 */
export function useRelatedEntries(entryId: string | undefined) {
  return useQuery<RelatedEntry[], Error>({
    queryKey: ["related-entries", entryId],
    queryFn: () => {
      if (!entryId) {
        throw new Error("Entry ID is required");
      }
      return fetchRelatedEntries(entryId);
    },
    enabled: Boolean(entryId),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes cache
  });
}
