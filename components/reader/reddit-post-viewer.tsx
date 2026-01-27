"use client";

import { formatDistanceToNow } from "date-fns";
import {
  ArrowUp,
  Clock,
  ExternalLink,
  Link as LinkIcon,
  Loader2,
  MessageSquare,
  User,
} from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import type { RedditComment, RedditPostDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

interface RedditPostViewerProps {
  post?: RedditPostDetail | null;
  comments?: RedditComment[];
  loading?: boolean;
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

function CommentItem({
  comment,
  isOp,
}: {
  comment: RedditComment;
  isOp?: boolean;
}) {
  const [collapsed, setCollapsed] = React.useState(false);

  return (
    <div
      className={cn(
        "border-l-2 border-border pl-3",
        comment.depth > 0 && "ml-3",
      )}
    >
      {/* Comment header */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="hover:text-foreground"
        >
          [{collapsed ? "+" : "-"}]
        </button>
        <span
          className={cn(
            "font-medium",
            comment.isSubmitter && "text-blue-500",
            comment.author === "[deleted]" && "text-muted-foreground italic",
          )}
        >
          {comment.author}
          {comment.isSubmitter && " (OP)"}
        </span>
        <span>•</span>
        <span>{formatNumber(comment.score)} points</span>
        <span>•</span>
        <span>
          {formatDistanceToNow(comment.createdAt, { addSuffix: true })}
        </span>
      </div>

      {/* Comment body */}
      {!collapsed && (
        <>
          <div
            className="prose prose-sm mt-1 max-w-none text-sm dark:prose-invert"
            dangerouslySetInnerHTML={{
              __html: comment.bodyHtml || comment.body,
            }}
          />

          {/* Replies */}
          {comment.replies.length > 0 && (
            <div className="mt-2 space-y-2">
              {comment.replies.map((reply) => (
                <CommentItem key={reply.id} comment={reply} isOp={isOp} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

export function RedditPostViewer({
  post,
  comments = [],
  loading = false,
}: RedditPostViewerProps) {
  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background">
        <Loader2 className="size-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!post) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background text-muted-foreground">
        <p>Select a post to read</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between border-b px-4 py-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">
            {post.subredditPrefixed}
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <User className="size-3" />
            u/{post.author}
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <Clock className="size-3" />
            {formatDistanceToNow(post.createdAt, { addSuffix: true })}
          </span>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <a
            href={`https://reddit.com${post.permalink}`}
            target="_blank"
            rel="noopener noreferrer"
          >
            <ExternalLink className="mr-1 size-4" />
            Reddit
          </a>
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <article className="p-4">
          {/* Title */}
          <h1 className="text-xl leading-tight font-bold">{post.title}</h1>

          {/* Flair */}
          {post.flair && (
            <span className="mt-2 inline-block rounded bg-muted px-2 py-0.5 text-xs">
              {post.flair}
            </span>
          )}

          {/* Stats */}
          <div className="mt-3 flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <ArrowUp className="size-4" />
              {formatNumber(post.score)} ({Math.round(post.upvoteRatio * 100)}%
              upvoted)
            </span>
            <span className="flex items-center gap-1">
              <MessageSquare className="size-4" />
              {formatNumber(post.numComments)} comments
            </span>
          </div>

          {/* Link post */}
          {!post.isSelf && (
            <a
              href={post.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 flex items-center gap-2 rounded-lg border p-3 text-sm hover:bg-accent"
            >
              <LinkIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate text-blue-500 hover:underline">
                {post.url}
              </span>
              <span className="shrink-0 text-xs text-muted-foreground">
                ({post.domain})
              </span>
            </a>
          )}

          {/* Preview image */}
          {post.previewUrl && !post.isVideo && (
            <div className="mt-4">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={post.previewUrl}
                alt=""
                className="max-h-[500px] rounded-lg object-contain"
              />
            </div>
          )}

          {/* Video */}
          {post.isVideo && post.videoUrl && (
            <div className="mt-4">
              <video
                src={post.videoUrl}
                controls
                className="max-h-[500px] w-full rounded-lg"
              />
            </div>
          )}

          {/* Self text */}
          {post.isSelf && post.selftextHtml && (
            <div
              className="prose prose-sm mt-4 max-w-none dark:prose-invert"
              dangerouslySetInnerHTML={{ __html: post.selftextHtml }}
            />
          )}

          {/* Comments section */}
          <div className="mt-8 border-t pt-4">
            <h2 className="mb-4 text-lg font-semibold">
              Comments ({formatNumber(post.numComments)})
            </h2>
            {comments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No comments yet</p>
            ) : (
              <div className="space-y-4">
                {comments.map((comment) => (
                  <CommentItem key={comment.id} comment={comment} />
                ))}
              </div>
            )}
          </div>
        </article>
      </div>
    </div>
  );
}
