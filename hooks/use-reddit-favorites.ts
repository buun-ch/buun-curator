/**
 * Hook for managing Reddit favorite subreddits.
 *
 * Provides CRUD operations for favorite subreddits with
 * TanStack Query for caching and mutations.
 *
 * @module hooks/use-reddit-favorites
 */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { isRedditEnabled } from "@/lib/config";

/** A favorite subreddit saved in the database. */
interface RedditFavorite {
  /** Unique ID of the favorite. */
  id: string;
  /** Subreddit name without r/ prefix. */
  name: string;
  /** Minimum score filter for this subreddit. */
  minScore: number;
  /** ISO timestamp when added to favorites. */
  createdAt: string;
}

/**
 * Fetches all favorite subreddits from the API.
 *
 * @returns Array of favorite subreddits
 */
async function fetchFavorites(): Promise<RedditFavorite[]> {
  const response = await fetch("/api/reddit/subreddits");
  if (!response.ok) {
    throw new Error("Failed to fetch favorites");
  }
  return response.json();
}

/**
 * Adds a subreddit to favorites.
 *
 * @param name - Subreddit name to add
 * @returns The created favorite
 */
async function addFavorite(name: string): Promise<RedditFavorite> {
  const response = await fetch("/api/reddit/subreddits", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || "Failed to add favorite");
  }
  return response.json();
}

/**
 * Removes a subreddit from favorites.
 *
 * @param id - Favorite ID to remove
 */
async function removeFavorite(id: string): Promise<void> {
  const response = await fetch(`/api/reddit/subreddits/${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to remove favorite");
  }
}

/**
 * Updates a favorite subreddit's settings.
 *
 * @param id - Favorite ID to update
 * @param data - Data to update (minScore)
 * @returns The updated favorite
 */
async function updateFavorite(
  id: string,
  data: { minScore?: number },
): Promise<RedditFavorite> {
  const response = await fetch(`/api/reddit/subreddits/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error("Failed to update favorite");
  }
  return response.json();
}

/**
 * Hook for managing Reddit favorite subreddits.
 *
 * Provides query for fetching favorites and mutations for
 * add, remove, and update operations. All mutations invalidate
 * the favorites cache on success.
 *
 * @returns Favorites list, loading states, and mutation functions
 */
export function useRedditFavorites() {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: ["reddit-favorites"],
    queryFn: fetchFavorites,
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: isRedditEnabled(),
  });

  const addMutation = useMutation({
    mutationFn: addFavorite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reddit-favorites"] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: removeFavorite,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reddit-favorites"] });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { minScore?: number } }) =>
      updateFavorite(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reddit-favorites"] });
    },
  });

  return {
    favorites: query.data ?? [],
    isLoading: query.isLoading,
    error: query.error,
    addFavorite: addMutation.mutateAsync,
    isAdding: addMutation.isPending,
    addError: addMutation.error,
    removeFavorite: removeMutation.mutateAsync,
    isRemoving: removeMutation.isPending,
    updateFavorite: (id: string, data: { minScore?: number }) =>
      updateMutation.mutateAsync({ id, data }),
    isUpdating: updateMutation.isPending,
  };
}
