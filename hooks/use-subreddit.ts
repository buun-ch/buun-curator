/**
 * Hook for fetching subreddit information with caching.
 *
 * Uses TanStack Query for caching and automatic refetching.
 * Subreddit info is cached for 10 minutes.
 *
 * @module hooks/use-subreddit
 */

"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchSubredditInfo } from "@/lib/reddit-api";
import type { SubredditInfo } from "@/lib/types";

/**
 * Hook for fetching subreddit information.
 *
 * Fetches metadata like subscriber count, description, and icon
 * for a given subreddit. Results are cached for 10 minutes.
 *
 * @param subredditName - Subreddit name without r/ prefix
 * @returns Query result with subreddit info and refetch function
 */
export function useSubreddit(subredditName: string | undefined) {
  const queryClient = useQueryClient();

  const query = useQuery<SubredditInfo, Error>({
    queryKey: ["subreddit", subredditName],
    queryFn: () => {
      if (!subredditName) {
        throw new Error("Subreddit name is required");
      }
      return fetchSubredditInfo(subredditName);
    },
    enabled: Boolean(subredditName),
    // Subreddit info doesn't change often, keep it fresh for 10 minutes
    staleTime: 10 * 60 * 1000,
    // Keep in cache for 1 hour
    gcTime: 60 * 60 * 1000,
  });

  const invalidateAndRefetch = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["subreddit", subredditName],
    });
    return query.refetch();
  };

  return {
    ...query,
    invalidateAndRefetch,
  };
}
