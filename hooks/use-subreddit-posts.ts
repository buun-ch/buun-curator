/**
 * Hook for fetching subreddit posts with infinite scroll.
 *
 * Uses TanStack Query's useInfiniteQuery for pagination.
 * Supports sorting, time filtering, and minimum score filtering.
 *
 * @module hooks/use-subreddit-posts
 */

"use client";

import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchSubredditPosts,
  type PostSortOption,
  type TimeFilterOption,
} from "@/lib/reddit-api";
import type { RedditPost } from "@/lib/types";

/** Options for the useSubredditPosts hook. */
interface UseSubredditPostsOptions {
  /** Sort order (hot, new, top, rising, controversial). */
  sort?: PostSortOption;
  /** Time filter for top/controversial (hour, day, week, month, year, all). */
  time?: TimeFilterOption;
  /** Number of posts per page. */
  limit?: number;
  /** Minimum score filter (client-side). */
  minScore?: number;
}

/**
 * Hook for fetching subreddit posts with infinite scroll.
 *
 * Fetches posts from a subreddit with pagination support.
 * Applies client-side minScore filtering after fetching.
 *
 * @param subredditName - Subreddit name without r/ prefix
 * @param options - Sort, time, limit, and minScore options
 * @returns Posts, pagination state, and control functions
 */
export function useSubredditPosts(
  subredditName: string | undefined,
  options: UseSubredditPostsOptions = {},
) {
  const { sort = "hot", time = "day", limit = 25, minScore = 0 } = options;
  const queryClient = useQueryClient();

  const query = useInfiniteQuery({
    queryKey: ["subreddit-posts", subredditName, sort, time, limit],
    queryFn: async ({ pageParam }) => {
      if (!subredditName) {
        throw new Error("Subreddit name is required");
      }
      return fetchSubredditPosts(subredditName, {
        sort,
        time,
        limit,
        after: pageParam,
      });
    },
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.after ?? undefined,
    enabled: Boolean(subredditName),
    staleTime: 60 * 1000, // 1 minute
    gcTime: 5 * 60 * 1000, // 5 minutes
  });

  // Flatten pages and apply minScore filter
  const allPosts: RedditPost[] =
    query.data?.pages.flatMap((page) => page.posts) ?? [];

  const filteredPosts =
    minScore > 0 ? allPosts.filter((post) => post.score >= minScore) : allPosts;

  const invalidateAndRefetch = async () => {
    await queryClient.invalidateQueries({
      queryKey: ["subreddit-posts", subredditName],
    });
    return query.refetch();
  };

  return {
    posts: filteredPosts,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    isFetchingNextPage: query.isFetchingNextPage,
    hasNextPage: query.hasNextPage,
    fetchNextPage: query.fetchNextPage,
    invalidateAndRefetch,
    error: query.error,
  };
}
