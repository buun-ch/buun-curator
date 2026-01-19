/**
 * Hook for fetching Reddit post details with comments.
 *
 * Uses TanStack Query for caching post data.
 * Results are cached for 1 minute.
 *
 * @module hooks/use-reddit-post
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchRedditPost } from "@/lib/reddit-api";
import type { RedditPostDetail, RedditComment } from "@/lib/types";

/**
 * Hook for fetching Reddit post details with comments.
 *
 * Fetches full post content and nested comment tree.
 * Results are cached for 1 minute.
 *
 * @param postId - Reddit post ID (without t3_ prefix)
 * @returns Query result with post detail and comments
 */
export function useRedditPost(postId: string | undefined) {
  return useQuery<{ post: RedditPostDetail; comments: RedditComment[] }, Error>(
    {
      queryKey: ["reddit-post", postId],
      queryFn: () => {
        if (!postId) {
          throw new Error("Post ID is required");
        }
        return fetchRedditPost(postId);
      },
      enabled: Boolean(postId),
      staleTime: 60 * 1000, // 1 minute
      gcTime: 5 * 60 * 1000, // 5 minutes
    },
  );
}
