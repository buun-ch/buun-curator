/**
 * Hook for managing Reddit browsing state.
 *
 * Coordinates subreddit info, posts, favorites, and search state
 * for the Reddit section of the reader.
 *
 * @module hooks/use-reddit-state
 */

"use client";

import * as React from "react";
import { useSubreddit } from "@/hooks/use-subreddit";
import { useSubredditPosts } from "@/hooks/use-subreddit-posts";
import { useRedditPost } from "@/hooks/use-reddit-post";
import { useRedditFavorites } from "@/hooks/use-reddit-favorites";
import { useSettingsStore } from "@/stores/settings-store";
import { useUrlState } from "@/lib/url-state-context";
import type {
  RedditPost,
  RedditPostDetail,
  RedditComment,
  ContentPanelMode,
  RedditFilterMode,
} from "@/lib/types";

/** Options for the useRedditState hook. */
export interface UseRedditStateOptions {
  /** Function to update the content panel mode. */
  setContentPanelMode: React.Dispatch<React.SetStateAction<ContentPanelMode>>;
}

/** Return value from the useRedditState hook. */
export interface UseRedditStateReturn {
  // Reddit search
  redditPosts: RedditPost[];
  redditSearchQuery: string;
  redditLoading: boolean;
  handleRedditSearch: (query: string) => void;

  // Selected post
  selectedRedditPost: RedditPost | null;
  setSelectedRedditPost: React.Dispatch<React.SetStateAction<RedditPost | null>>;
  redditPostData:
    | { post: RedditPostDetail; comments: RedditComment[] }
    | undefined;
  redditPostLoading: boolean;

  // Subreddit
  selectedSubredditName: string | undefined;
  subredditInfo: ReturnType<typeof useSubreddit>["data"];
  showSubredditLoading: boolean;

  // Subreddit posts
  subredditPosts: RedditPost[];
  postsLoading: boolean;
  postsLoadingMore: boolean;
  hasMorePosts: boolean;
  fetchMorePosts: () => void;

  // Subreddit filter
  currentSubredditFilterMode: RedditFilterMode;
  setSubredditFilterMode: (subreddit: string, mode: RedditFilterMode) => void;

  // Favorite management
  currentFavoriteId: string | null;
  currentFavoriteMinScore: number;
  updateFavoriteSubreddit: (
    id: string,
    data: { minScore?: number }
  ) => void;
  handleRemoveFavorite: () => Promise<void>;
  isRemovingFavorite: boolean;

  // Refresh
  handleRefreshSubreddit: () => Promise<void>;
  isRefreshingSubreddit: boolean;
}

/**
 * Hook for managing Reddit browsing state.
 *
 * Combines multiple Reddit-related hooks to provide a unified
 * interface for subreddit browsing, post viewing, favorites,
 * and search functionality.
 *
 * @param options - Hook options with subscription state
 * @returns Reddit state and control functions
 */
export function useRedditState({
  setContentPanelMode,
}: UseRedditStateOptions): UseRedditStateReturn {
  // URL state for navigation
  const { selectedSubscription, navigateToAllEntries } = useUrlState();
  // Reddit search state
  const [redditPosts, setRedditPosts] = React.useState<RedditPost[]>([]);
  const [redditSearchQuery, setRedditSearchQuery] = React.useState("");
  const [redditLoading, setRedditLoading] = React.useState(false);
  const [selectedRedditPost, setSelectedRedditPost] =
    React.useState<RedditPost | null>(null);

  // Selected subreddit name (shared via store across components)
  const selectedSubredditName = useSettingsStore(
    (state) => state.selectedSubredditName
  );
  const setSelectedSubredditName = useSettingsStore(
    (state) => state.setSelectedSubredditName
  );

  // Settings from store (persisted to localStorage)
  const getSubredditFilterMode = useSettingsStore(
    (state) => state.getSubredditFilterMode
  );
  const setSubredditFilterMode = useSettingsStore(
    (state) => state.setSubredditFilterMode
  );

  // Get current subreddit filter mode from localStorage
  const currentSubredditFilterMode = selectedSubredditName
    ? getSubredditFilterMode(selectedSubredditName)
    : ("all" as const);

  // Fetch Reddit favorites for subreddit name lookup, removal, and minScore
  const {
    favorites: redditFavorites,
    removeFavorite: removeFavoriteSubreddit,
    updateFavorite: updateFavoriteSubreddit,
  } = useRedditFavorites();

  // Get current favorite ID from selection
  const currentFavoriteId = React.useMemo(() => {
    if (selectedSubscription?.startsWith("reddit-fav-")) {
      return selectedSubscription.replace("reddit-fav-", "");
    }
    return null;
  }, [selectedSubscription]);

  // Get current favorite's minScore from DB (via favorites list)
  const currentFavoriteMinScore = React.useMemo(() => {
    if (!currentFavoriteId) return 0;
    const favorite = redditFavorites.find((f) => f.id === currentFavoriteId);
    return favorite?.minScore ?? 0;
  }, [currentFavoriteId, redditFavorites]);

  // Fetch subreddit info using React Query
  const {
    data: subredditInfo,
    isLoading: subredditLoading,
    isFetching: subredditFetching,
    invalidateAndRefetch: refetchSubredditInfo,
  } = useSubreddit(selectedSubredditName);

  // Show loading when fetching (isLoading is only true on first fetch)
  const showSubredditLoading = subredditLoading || subredditFetching;

  // Fetch subreddit posts (minScore comes from DB via favorites)
  const {
    posts: subredditPosts,
    isLoading: postsLoading,
    isFetchingNextPage: postsLoadingMore,
    hasNextPage: hasMorePosts,
    fetchNextPage: fetchMorePosts,
    invalidateAndRefetch: refetchSubredditPosts,
  } = useSubredditPosts(selectedSubredditName, {
    minScore: currentFavoriteMinScore,
  });

  // Track refreshing state for subreddit
  const [isRefreshingSubreddit, setIsRefreshingSubreddit] =
    React.useState(false);

  // Handle refresh of subreddit info and posts
  const handleRefreshSubreddit = React.useCallback(async () => {
    setIsRefreshingSubreddit(true);
    try {
      await Promise.all([refetchSubredditInfo(), refetchSubredditPosts()]);
    } finally {
      setIsRefreshingSubreddit(false);
    }
  }, [refetchSubredditInfo, refetchSubredditPosts]);

  // Fetch selected Reddit post details
  const { data: redditPostData, isLoading: redditPostLoading } = useRedditPost(
    selectedRedditPost?.id
  );

  // Track removing favorite state
  const [isRemovingFavorite, setIsRemovingFavorite] = React.useState(false);

  // Handle removing current favorite subreddit
  const handleRemoveFavorite = React.useCallback(async () => {
    if (!currentFavoriteId) return;
    setIsRemovingFavorite(true);
    try {
      await removeFavoriteSubreddit(currentFavoriteId);
      // Navigate to "all" after removal
      navigateToAllEntries();
      setContentPanelMode("entries");
      setSelectedSubredditName(undefined);
    } finally {
      setIsRemovingFavorite(false);
    }
  }, [
    currentFavoriteId,
    removeFavoriteSubreddit,
    navigateToAllEntries,
    setContentPanelMode,
    setSelectedSubredditName,
  ]);

  // Handle Reddit search
  const handleRedditSearch = React.useCallback((query: string) => {
    setRedditSearchQuery(query);
    setRedditLoading(true);
    // TODO: Replace with actual Reddit API call
    setTimeout(() => {
      setRedditPosts([
        {
          id: "1",
          title: `Search results for "${query}" - Example Post 1`,
          subreddit: "programming",
          author: "example_user",
          score: 1234,
          numComments: 89,
          createdAt: new Date(Date.now() - 3600000),
          url: "https://example.com",
          permalink: "/r/programming/comments/abc123",
          selftext: "This is an example post about the search query...",
          isNsfw: false,
        },
        {
          id: "2",
          title: `Another result for "${query}" - Discussion Thread`,
          subreddit: "webdev",
          author: "another_user",
          score: 567,
          numComments: 45,
          createdAt: new Date(Date.now() - 7200000),
          url: "https://example.com/2",
          permalink: "/r/webdev/comments/def456",
          isNsfw: false,
        },
      ]);
      setRedditLoading(false);
    }, 500);
  }, []);

  return {
    // Reddit search
    redditPosts,
    redditSearchQuery,
    redditLoading,
    handleRedditSearch,

    // Selected post
    selectedRedditPost,
    setSelectedRedditPost,
    redditPostData,
    redditPostLoading,

    // Subreddit
    selectedSubredditName,
    subredditInfo,
    showSubredditLoading,

    // Subreddit posts
    subredditPosts,
    postsLoading,
    postsLoadingMore,
    hasMorePosts: hasMorePosts ?? false,
    fetchMorePosts,

    // Subreddit filter
    currentSubredditFilterMode,
    setSubredditFilterMode,

    // Favorite management
    currentFavoriteId,
    currentFavoriteMinScore,
    updateFavoriteSubreddit,
    handleRemoveFavorite,
    isRemovingFavorite,

    // Refresh
    handleRefreshSubreddit,
    isRefreshingSubreddit,
  };
}
