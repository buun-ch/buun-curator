"use client";

import * as React from "react";
import Image from "next/image";
import { formatDistanceToNowStrict } from "date-fns";

import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { useRelatedEntries } from "@/hooks/use-related-entries";
import type { RelatedEntry } from "@/lib/types";

interface RelatedEntriesSectionProps {
  entryId: string;
  onEntryClick?: (entryId: string) => void;
}

interface RelatedEntryCardProps {
  entry: RelatedEntry;
  onClick?: () => void;
}

/**
 * Card component for displaying a related entry.
 */
function RelatedEntryCard({ entry, onClick }: RelatedEntryCardProps) {
  const source = entry.feedName || "Unknown";
  const publishedAt = entry.publishedAt ? new Date(entry.publishedAt) : null;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "group flex w-48 shrink-0 cursor-pointer flex-col gap-2 rounded-lg border-1 p-3",
        "text-left transition-colors hover:bg-accent",
      )}
    >
      {/* Thumbnail */}
      {entry.thumbnailUrl ? (
        <Image
          src={entry.thumbnailUrl}
          alt=""
          width={176}
          height={96}
          className="h-24 w-full rounded-md border-1 object-cover"
          unoptimized
        />
      ) : (
        <div className="flex h-24 w-full items-center justify-center rounded-md border-1 bg-muted">
          <span className="text-3xl text-muted-foreground">
            {source.charAt(0)}
          </span>
        </div>
      )}

      {/* Title */}
      <h4 className="line-clamp-2 text-sm font-medium">{entry.title}</h4>

      {/* Meta */}
      <div className="mt-auto flex items-center gap-2 text-xs text-muted-foreground">
        <span className="truncate">{source}</span>
        {publishedAt && (
          <>
            <span>·</span>
            <span className="shrink-0">
              {formatDistanceToNowStrict(publishedAt, { addSuffix: true })}
            </span>
          </>
        )}
      </div>
    </button>
  );
}

/**
 * Skeleton placeholder for loading state.
 */
function RelatedEntryCardSkeleton() {
  return (
    <div className="flex w-48 shrink-0 flex-col gap-2 rounded-lg border-1 p-3">
      <Skeleton className="h-24 w-full rounded-md" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="mt-auto h-3 w-1/2" />
    </div>
  );
}

/**
 * Section component for displaying related entries.
 *
 * Shows horizontally scrollable cards of related entries.
 * Hidden when there are no related entries or on error.
 */
export function RelatedEntriesSection({
  entryId,
  onEntryClick,
}: RelatedEntriesSectionProps) {
  const { data: entries, isLoading, isError } = useRelatedEntries(entryId);

  // Hide on error
  if (isError) {
    return null;
  }

  // Hide when no related entries (after loading)
  if (!isLoading && (!entries || entries.length === 0)) {
    return null;
  }

  return (
    <section className="mt-8 border-t pt-6">
      <h3 className="mb-4 text-sm font-medium text-muted-foreground">
        Related Entries
      </h3>

      <div className="flex gap-3 overflow-x-auto pb-2">
        {isLoading ? (
          // Loading skeleton
          <>
            <RelatedEntryCardSkeleton />
            <RelatedEntryCardSkeleton />
            <RelatedEntryCardSkeleton />
          </>
        ) : (
          // Render related entries
          entries?.map((entry) => (
            <RelatedEntryCard
              key={entry.id}
              entry={entry}
              onClick={() => onEntryClick?.(entry.id)}
            />
          ))
        )}
      </div>
    </section>
  );
}
