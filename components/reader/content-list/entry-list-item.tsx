"use client";

import * as React from "react";
import Image from "next/image";
import { formatDistanceToNowStrict } from "date-fns";
import ReactMarkdown from "react-markdown";
import { Star, Circle } from "lucide-react";

import { cn } from "@/lib/utils";

import type { EntryListItemComponentProps } from "./types";

/**
 * Entry list item component for the content list.
 *
 * Displays thumbnail, title, summary, source, and publish time.
 */
export const EntryListItem = React.forwardRef<HTMLDivElement, EntryListItemComponentProps>(
  function EntryListItem({ entry, isSelected, onSelect, onToggleStar }, ref) {
    const source = entry.feedName || "Unknown";
    const publishedAt = entry.publishedAt
      ? new Date(entry.publishedAt)
      : new Date(entry.createdAt);

    return (
      <div
        ref={ref}
        role="button"
        tabIndex={0}
        onClick={() => onSelect?.(entry)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            onSelect?.(entry);
          }
        }}
        className={cn(
          "group flex w-full cursor-pointer gap-3 p-2.5 text-left transition-colors hover:bg-accent select-none",
          isSelected && "bg-accent",
          !entry.isRead && "bg-accent/30"
        )}
      >
        {/* Thumbnail */}
        {entry.thumbnailUrl ? (
          <Image
            src={entry.thumbnailUrl}
            alt=""
            width={64}
            height={64}
            className="size-16 shrink-0 rounded-md border border-border/50 object-cover grayscale-70"
            unoptimized
          />
        ) : (
          <div className="flex size-16 shrink-0 items-center justify-center rounded-md border border-border/50 bg-muted">
            <span className="text-2xl text-muted-foreground">
              {source.charAt(0)}
            </span>
          </div>
        )}

        {/* Content */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-start gap-2">
            {/* Unread indicator */}
            {!entry.isRead && (
              <Circle className="mt-1.5 size-2 shrink-0 fill-primary text-primary" />
            )}
            <h3
              className={cn(
                "line-clamp-2 flex-1 text-sm",
                !entry.isRead && "font-semibold"
              )}
            >
              {entry.title}
            </h3>
            {/* Star button */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggleStar?.(entry);
              }}
              className={cn(
                "shrink-0 p-1 hover:text-foreground",
                entry.isStarred
                  ? "text-neutral-500"
                  : "text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
              )}
            >
              <Star
                className={cn("size-4", entry.isStarred && "fill-current")}
              />
            </button>
          </div>

          {entry.summary && (
            <div className="prose prose-xs prose-neutral dark:prose-invert mt-1 line-clamp-2 max-w-none text-xs text-muted-foreground [&>*]:m-0 [&_li]:my-0 [&_ol]:my-0 [&_ul]:my-0">
              <ReactMarkdown>{entry.summary}</ReactMarkdown>
            </div>
          )}

          <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="truncate font-medium">{source}</span>
            <span className="ml-auto shrink-0">
              {formatDistanceToNowStrict(publishedAt, {
                addSuffix: true,
              })}
            </span>
          </div>
        </div>
      </div>
    );
  }
);
