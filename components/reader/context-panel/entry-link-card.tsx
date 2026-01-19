"use client";

import {
  ExternalLink,
  Link2,
  Plus,
  Loader2,
  Clock,
  AlertCircle,
  RotateCcw,
} from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { GroupedEntryLink } from "./types";

interface EntryLinkCardProps {
  link: GroupedEntryLink;
  isPending?: boolean;
  isFetching?: boolean;
  isError?: boolean;
  errorMessage?: string;
  onEnrich?: (url: string) => void;
}

/**
 * Card component for displaying grouped entry links.
 *
 * Shows URL and list of titles with enrich button.
 */
export function EntryLinkCard({
  link,
  isPending = false,
  isFetching = false,
  isError = false,
  errorMessage,
  onEnrich,
}: EntryLinkCardProps) {
  const isProcessing = isPending || isFetching;

  // Determine button icon and title
  const getButtonContent = () => {
    if (isFetching) {
      return {
        icon: <Loader2 className="h-4 w-4 animate-spin" />,
        title: "Fetching content...",
      };
    }
    if (isPending) {
      return {
        icon: <Clock className="h-4 w-4" />,
        title: "Queued for fetching",
      };
    }
    if (isError) {
      return {
        icon: <RotateCcw className="h-4 w-4" />,
        title: "Retry fetch",
      };
    }
    return {
      icon: <Plus className="h-4 w-4" />,
      title: "Add to enrichments",
    };
  };

  const { icon: buttonIcon, title: buttonTitle } = getButtonContent();

  return (
    <div
      className={cn(
        "flex min-h-[60px] w-[calc(50%-0.25rem)] items-start gap-2 rounded-lg border p-2",
        isPending && "border-yellow-500/50 bg-yellow-500/5",
        isFetching && "border-blue-500/50 bg-blue-500/5",
        isError && "border-destructive/50 bg-destructive/5",
        !isProcessing && !isError && "border-border",
      )}
    >
      {/* Link icon or error icon */}
      {isError ? (
        <Tooltip>
          <TooltipTrigger asChild>
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
          </TooltipTrigger>
          <TooltipContent side="top" className="max-w-[300px]">
            <p className="text-xs">{errorMessage || "Failed to fetch"}</p>
          </TooltipContent>
        </Tooltip>
      ) : (
        <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
      )}

      {/* Link info */}
      <div className="min-w-0 flex-1 space-y-1">
        {/* URL (full, truncated) */}
        <p
          className={cn(
            "truncate text-xs font-medium",
            isError ? "text-destructive" : "text-foreground",
          )}
        >
          {link.url}
        </p>

        {/* Error message */}
        {isError && errorMessage && (
          <p
            className="truncate text-xs text-destructive/80"
            title={errorMessage}
          >
            {errorMessage}
          </p>
        )}

        {/* Titles list */}
        {!isError && link.titles.length > 0 && (
          <ul className="space-y-0.5">
            {link.titles.map((title, i) => (
              <li
                key={i}
                className="truncate text-xs text-muted-foreground"
                title={title}
              >
                {title}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Action buttons */}
      <div className="flex shrink-0 flex-col gap-1">
        <button
          type="button"
          onClick={() => onEnrich?.(link.url)}
          disabled={isProcessing}
          className={cn(
            "rounded p-1",
            isProcessing
              ? "cursor-not-allowed text-muted-foreground/50"
              : isError
                ? "text-destructive hover:bg-destructive/10 hover:text-destructive"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
          )}
          title={buttonTitle}
        >
          {buttonIcon}
        </button>
        <a
          href={link.url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          title="Open in new tab"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
    </div>
  );
}
