"use client";

import * as React from "react";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowUp,
  MessageSquare,
  Loader2,
  Search,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import type { RedditPost } from "@/lib/types";

interface RedditSearchResultsProps {
  posts?: RedditPost[];
  loading?: boolean;
  searchQuery?: string;
  onSearch?: (query: string) => void;
  selectedId?: string;
  onSelect?: (post: RedditPost) => void;
}

function RedditPostItem({
  post,
  isSelected,
  onSelect,
}: {
  post: RedditPost;
  isSelected?: boolean;
  onSelect?: (post: RedditPost) => void;
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
      {/* Vote count */}
      <div className="flex flex-col items-center justify-start gap-1 text-muted-foreground">
        <ArrowUp className="size-4" />
        <span className="text-xs font-medium">{formatScore(post.score)}</span>
      </div>

      {/* Content */}
      <div className="flex min-w-0 flex-1 flex-col">
        <h3 className="line-clamp-2 text-sm font-medium">{post.title}</h3>

        {post.selftext && (
          <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
            {post.selftext}
          </p>
        )}

        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span className="font-medium">r/{post.subreddit}</span>
          <span>•</span>
          <span>u/{post.author}</span>
          <span>•</span>
          <span>{formatDistanceToNow(post.createdAt, { addSuffix: true })}</span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <MessageSquare className="size-3" />
            {post.numComments}
          </span>
        </div>
      </div>

      {/* External link */}
      <a
        href={`https://reddit.com${post.permalink}`}
        target="_blank"
        rel="noopener noreferrer"
        onClick={(e) => e.stopPropagation()}
        className="shrink-0 p-1 text-muted-foreground hover:text-foreground"
      >
        <ExternalLink className="size-4" />
      </a>
    </div>
  );
}

function formatScore(score: number): string {
  if (score >= 10000) {
    return `${(score / 1000).toFixed(1)}k`;
  }
  if (score >= 1000) {
    return `${(score / 1000).toFixed(1)}k`;
  }
  return score.toString();
}

export function RedditSearchResults({
  posts = [],
  loading = false,
  searchQuery = "",
  onSearch,
  selectedId,
  onSelect,
}: RedditSearchResultsProps) {
  const [inputValue, setInputValue] = React.useState(searchQuery);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      onSearch?.(inputValue.trim());
    }
  };

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header with search */}
      <div className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
        <form onSubmit={handleSubmit} className="flex flex-1 items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search Reddit..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              className="h-8 pl-8"
            />
          </div>
          <Button type="submit" size="sm" variant="secondary">
            Search
          </Button>
        </form>
      </div>

      {/* Results list */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-6 animate-spin text-muted-foreground" />
          </div>
        ) : posts.length === 0 ? (
          <Empty className="py-8">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <Search className="h-5 w-5" />
              </EmptyMedia>
              <EmptyTitle>
                {searchQuery ? "No Results Found" : "Search Reddit"}
              </EmptyTitle>
              <EmptyDescription>
                {searchQuery
                  ? "Try adjusting your search query."
                  : "Enter a search query to find posts."}
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="divide-y">
            {posts.map((post) => (
              <RedditPostItem
                key={post.id}
                post={post}
                isSelected={selectedId === post.id}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
