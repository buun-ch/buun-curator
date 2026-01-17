"use client";

import { format } from "date-fns";

import type { Entry } from "@/lib/types";
import { EntryLabels } from "./entry-labels";

interface EntryHeaderProps {
  entry: Entry;
}

/**
 * Entry header component.
 *
 * Displays source, date, title, author, and labels.
 */
export function EntryHeader({ entry }: EntryHeaderProps) {
  const publishedAt = entry.publishedAt
    ? new Date(entry.publishedAt)
    : new Date(entry.createdAt);

  return (
    <header className="mb-4">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <span className="font-medium text-foreground">
          {entry.feedName || "Unknown"}
        </span>
        <span>•</span>
        <span>{format(publishedAt, "MMMM d, yyyy")}</span>
        <span>|</span>
        <span>{format(publishedAt, "HH:mm")}</span>
      </div>

      <a
        href={entry.url}
        target="_blank"
        rel="noopener noreferrer"
        className="-mx-2 mb-4 block rounded-md p-2 transition-colors hover:bg-accent"
      >
        <h1 className="text-3xl font-bold leading-tight">{entry.title}</h1>
      </a>

      {/* Labels */}
      <EntryLabels entryId={entry.id} labels={entry.labels} />

      {entry.author && (
        <p className="mt-2 text-sm text-muted-foreground">By {entry.author}</p>
      )}
    </header>
  );
}
