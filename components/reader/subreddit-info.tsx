"use client";

import * as React from "react";
import Image from "next/image";
import { formatDistanceToNow } from "date-fns";
import {
  Users,
  Calendar,
  Loader2,
  AlertTriangle,
  UserCheck,
  Star,
  Circle,
  Inbox,
  ChevronUp,
  ChevronDown,
  ArrowUp,
  MessageSquare,
  Trash2,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { useSubreddit } from "@/hooks/use-subreddit";
import { useSubredditPosts } from "@/hooks/use-subreddit-posts";
import { useRedditFavorites } from "@/hooks/use-reddit-favorites";
import { useSettingsStore } from "@/stores/settings-store";
import type { RedditFilterMode, RedditPost } from "@/lib/types";

interface SubredditInfoProps {
  subredditName?: string;
  favoriteId?: string;
  selectedPostId?: string;
  onSelectPost?: (post: RedditPost) => void;
  onBrowse?: () => void;
  onRemoved?: () => void;
}

function formatNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`;
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`;
  }
  return num.toString();
}

function PostItem({
  post,
  isSelected,
  onSelect,
  onToggleStar,
}: {
  post: RedditPost;
  isSelected?: boolean;
  onSelect?: (post: RedditPost) => void;
  onToggleStar?: (post: RedditPost) => void;
}) {
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect?.(post)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect?.(post);
        }
      }}
      className={cn(
        "flex w-full cursor-pointer gap-3 p-3 text-left transition-colors hover:bg-accent select-none",
        isSelected && "bg-accent"
      )}
    >
      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-start gap-2">
          <h3 className="line-clamp-2 flex-1 text-sm">{post.title}</h3>
          {/* Star button */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleStar?.(post);
            }}
            className="shrink-0 p-1 text-muted-foreground hover:text-yellow-500"
          >
            <Star className="size-4" />
          </button>
        </div>

        <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <ArrowUp className="size-3" />
            {formatNumber(post.score)}
          </span>
          <span className="flex items-center gap-1">
            <MessageSquare className="size-3" />
            {formatNumber(post.numComments)}
          </span>
          <span>
            {formatDistanceToNow(post.createdAt, { addSuffix: true })}
          </span>
        </div>
      </div>
    </div>
  );
}

export function SubredditInfo({
  subredditName,
  favoriteId,
  selectedPostId,
  onSelectPost,
  onBrowse,
  onRemoved,
}: SubredditInfoProps) {
  // Get favorite data for minScore
  const { favorites, updateFavorite, removeFavorite } = useRedditFavorites();
  const favorite = favoriteId
    ? favorites.find((f) => f.id === favoriteId)
    : undefined;
  const minScore = favorite?.minScore ?? 0;

  // Filter mode from settings store
  const getSubredditFilterMode = useSettingsStore(
    (state) => state.getSubredditFilterMode
  );
  const setSubredditFilterMode = useSettingsStore(
    (state) => state.setSubredditFilterMode
  );
  const filterMode = subredditName
    ? getSubredditFilterMode(subredditName)
    : "all";

  // Fetch subreddit info
  const {
    data: subreddit,
    isLoading: subredditLoading,
    isFetching: subredditFetching,
    invalidateAndRefetch: refetchSubredditInfo,
  } = useSubreddit(subredditName);

  // Fetch subreddit posts
  const {
    posts,
    isLoading: postsLoading,
    isFetchingNextPage: postsLoadingMore,
    hasNextPage: hasMorePosts,
    fetchNextPage: fetchMorePosts,
    invalidateAndRefetch: refetchSubredditPosts,
  } = useSubredditPosts(subredditName, { minScore });

  // Refreshing state
  const [isRefreshing, setIsRefreshing] = React.useState(false);
  const handleRefresh = React.useCallback(async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([refetchSubredditInfo(), refetchSubredditPosts()]);
    } finally {
      setIsRefreshing(false);
    }
  }, [refetchSubredditInfo, refetchSubredditPosts]);

  // Remove favorite state
  const [isRemovingFavorite, setIsRemovingFavorite] = React.useState(false);
  const handleRemoveFavorite = React.useCallback(async () => {
    if (!favoriteId) return;
    setIsRemovingFavorite(true);
    try {
      await removeFavorite(favoriteId);
      onRemoved?.();
    } finally {
      setIsRemovingFavorite(false);
    }
  }, [favoriteId, removeFavorite, onRemoved]);

  // Min score handlers
  const handleMinScoreChange = React.useCallback(
    (score: number) => {
      if (favoriteId) {
        updateFavorite(favoriteId, { minScore: score });
      }
    },
    [favoriteId, updateFavorite]
  );

  // Filter mode handler
  const handleFilterModeChange = React.useCallback(
    (mode: RedditFilterMode) => {
      if (subredditName) {
        setSubredditFilterMode(subredditName, mode);
      }
    },
    [subredditName, setSubredditFilterMode]
  );

  // Intersection Observer for infinite scroll
  const loadMoreRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!hasMorePosts || !fetchMorePosts) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !postsLoadingMore) {
          fetchMorePosts();
        }
      },
      { threshold: 0.1 }
    );

    const currentRef = loadMoreRef.current;
    if (currentRef) {
      observer.observe(currentRef);
    }

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [hasMorePosts, postsLoadingMore, fetchMorePosts]);

  // Local state for min score input
  const [scoreInput, setScoreInput] = React.useState(minScore.toString());

  // Sync input when prop changes
  React.useEffect(() => {
    setScoreInput(minScore.toString());
  }, [minScore]);

  const handleScoreInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setScoreInput(value);
    const parsed = parseInt(value, 10);
    if (!isNaN(parsed) && parsed >= 0) {
      handleMinScoreChange(parsed);
    }
  };

  const incrementScore = () => {
    const newScore = minScore + 10;
    setScoreInput(newScore.toString());
    handleMinScoreChange(newScore);
  };

  const decrementScore = () => {
    const newScore = Math.max(0, minScore - 10);
    setScoreInput(newScore.toString());
    handleMinScoreChange(newScore);
  };

  const loading = subredditLoading || subredditFetching;

  if (loading) {
    return (
      <div className="flex h-full flex-col bg-background">
        <div className="flex flex-1 items-center justify-center">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      </div>
    );
  }

  if (!subreddit) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <Users className="h-5 w-5" />
            </EmptyMedia>
            <EmptyTitle>No Subreddit Selected</EmptyTitle>
            <EmptyDescription>
              Choose a subreddit from the sidebar to view its info.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Banner with icon overlay */}
      <div className="relative shrink-0">
        {subreddit.bannerUrl ? (
          <div className="relative h-24 bg-gradient-to-r from-orange-500 to-orange-600">
            <Image
              src={subreddit.bannerUrl}
              alt=""
              fill
              className="object-cover"
              unoptimized
            />
          </div>
        ) : (
          <div className="h-24 bg-gradient-to-r from-orange-500 to-orange-600" />
        )}

        {/* Icon - positioned to overlap banner */}
        <div className="absolute -bottom-8 left-4 z-10">
          {subreddit.iconUrl ? (
            <div className="rounded-full bg-white p-1">
              <Image
                src={subreddit.iconUrl}
                alt=""
                width={64}
                height={64}
                className="size-16 rounded-full object-cover"
                unoptimized
              />
            </div>
          ) : (
            <div className="rounded-full bg-white p-1">
              <div className="flex size-16 items-center justify-center rounded-full bg-orange-500">
                <span className="text-2xl font-bold text-white">
                  {subreddit.displayName.charAt(0).toUpperCase()}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 pt-12">
        {/* Header */}
        <div className="flex items-center gap-2">
          <h1 className="text-lg font-bold truncate flex-1">
            r/{subreddit.displayName}
          </h1>
          {subreddit.isNsfw && (
            <span className="flex items-center gap-1 rounded bg-red-500/10 px-1.5 py-0.5 text-xs font-medium text-red-500">
              <AlertTriangle className="size-3" />
              NSFW
            </span>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="size-8 shrink-0 text-muted-foreground"
            onClick={handleRefresh}
            disabled={isRefreshing}
            title="Refresh"
          >
            <RefreshCw
              className={cn("size-4", isRefreshing && "animate-spin")}
            />
          </Button>
          {favoriteId && (
            <Button
              variant="ghost"
              size="icon"
              className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
              onClick={handleRemoveFavorite}
              disabled={isRemovingFavorite}
              title="Remove from favorites"
            >
              {isRemovingFavorite ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Trash2 className="size-4" />
              )}
            </Button>
          )}
        </div>
        {subreddit.title && subreddit.title !== subreddit.displayName && (
          <p className="text-sm text-muted-foreground truncate">
            {subreddit.title}
          </p>
        )}

        {/* Stats */}
        <div className="mt-4 flex flex-wrap gap-4">
          <div className="flex items-center gap-2 text-sm">
            <Users className="size-4 text-muted-foreground" />
            <span className="font-medium">
              {formatNumber(subreddit.subscribers)}
            </span>
            <span className="text-muted-foreground">members</span>
          </div>

          {subreddit.activeUsers && (
            <div className="flex items-center gap-2 text-sm">
              <UserCheck className="size-4 text-green-500" />
              <span className="font-medium">
                {formatNumber(subreddit.activeUsers)}
              </span>
              <span className="text-muted-foreground">online</span>
            </div>
          )}

          <div className="flex items-center gap-2 text-sm">
            <Calendar className="size-4 text-muted-foreground" />
            <span className="text-muted-foreground">
              Created{" "}
              {formatDistanceToNow(subreddit.createdAt, { addSuffix: true })}
            </span>
          </div>
        </div>

        {/* Description */}
        {subreddit.description && (
          <div className="mt-4">
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {subreddit.description}
            </p>
          </div>
        )}

        {/* Filter settings */}
        <div className="mt-4 -mx-4 border-t pt-3 px-4">
          <div className="flex items-center gap-3">
            {/* Min score control */}
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">Min Score</span>
              <div className="flex items-center">
                <Button
                  variant="outline"
                  size="icon"
                  className="h-6 w-6 rounded-r-none"
                  onClick={decrementScore}
                  disabled={minScore <= 0}
                >
                  <ChevronDown className="size-3" />
                </Button>
                <Input
                  type="number"
                  value={scoreInput}
                  onChange={handleScoreInputChange}
                  className="h-6 w-12 rounded-none border-x-0 text-center text-xs [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  min={0}
                />
                <Button
                  variant="outline"
                  size="icon"
                  className="h-6 w-6 rounded-l-none"
                  onClick={incrementScore}
                >
                  <ChevronUp className="size-3" />
                </Button>
              </div>
            </div>

            {/* Filter mode toggle */}
            <ToggleGroup
              type="single"
              value={filterMode}
              onValueChange={(value) => {
                if (value) handleFilterModeChange(value as RedditFilterMode);
              }}
              size="sm"
              variant="outline"
              className="h-6"
            >
              <ToggleGroupItem
                value="starred"
                aria-label="Starred"
                title="Starred"
                className="h-6 w-6 p-0"
              >
                <Star className="size-3" />
              </ToggleGroupItem>
              <ToggleGroupItem
                value="unread"
                aria-label="Unread"
                title="Unread"
                className="h-6 w-6 p-0"
              >
                <Circle className="size-3" />
              </ToggleGroupItem>
              <ToggleGroupItem
                value="all"
                aria-label="All"
                title="All"
                className="h-6 w-6 p-0"
              >
                <Inbox className="size-3" />
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>

        {/* Posts list */}
        <div className="mt-4 -mx-4 border-t">
          {postsLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : posts.length === 0 ? (
            <Empty className="py-8">
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <Inbox className="h-5 w-5" />
                </EmptyMedia>
                <EmptyTitle>No Posts</EmptyTitle>
                <EmptyDescription>
                  No posts match the current filter.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="divide-y">
              {posts.map((post) => (
                <PostItem
                  key={post.id}
                  post={post}
                  isSelected={selectedPostId === post.id}
                  onSelect={onSelectPost}
                />
              ))}
              {/* Infinite scroll trigger */}
              {hasMorePosts && (
                <div
                  ref={loadMoreRef}
                  className="flex items-center justify-center py-4"
                >
                  {postsLoadingMore ? (
                    <Loader2 className="size-5 animate-spin text-muted-foreground" />
                  ) : (
                    <span className="text-xs text-muted-foreground">
                      Scroll for more
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
