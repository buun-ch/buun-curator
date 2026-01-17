"use client";

import { Globe, Check, ExternalLink, X, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

import type { WebPage } from "./types";

/** Web page with URL for display. */
interface WebPageWithUrl extends WebPage {
  url: string;
}

interface WebPageCardProps {
  page: WebPageWithUrl;
  isSelected: boolean;
  isDeleting?: boolean;
  onToggleSelect: (url: string) => void;
  onDelete?: (url: string) => void;
}

/**
 * Card component for displaying a web page reference.
 *
 * Supports selection for context inclusion.
 */
export function WebPageCard({
  page,
  isSelected,
  isDeleting,
  onToggleSelect,
  onDelete,
}: WebPageCardProps) {
  return (
    <div
      className={cn(
        "group flex h-[100px] w-[320px] items-start gap-3 rounded-lg border p-3 transition-colors",
        isSelected ? "border-primary bg-primary/5" : "border-border",
        isDeleting && "opacity-50"
      )}
    >
      {/* Selection checkbox */}
      <button
        type="button"
        onClick={() => onToggleSelect(page.url)}
        disabled={isDeleting}
        className={cn(
          "mt-0.5 flex h-4 w-4 shrink-0 cursor-pointer items-center justify-center rounded-sm border transition-colors",
          isSelected
            ? "border-primary bg-primary text-primary-foreground"
            : "border-muted-foreground/30 hover:border-muted-foreground",
          isDeleting && "cursor-not-allowed"
        )}
      >
        {isSelected && <Check className="h-3 w-3" />}
      </button>

      {/* Page info */}
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* Line 1: Globe icon + title + actions */}
        <div className="flex items-center gap-1.5">
          <Globe className="h-4 w-4 shrink-0 text-muted-foreground" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium">
            {page.title || "Untitled"}
          </span>
          <a
            href={page.url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Open in new tab"
          >
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
          {/* Delete button */}
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(page.url)}
              disabled={isDeleting}
              className={cn(
                "shrink-0 rounded p-0.5 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100",
                "hover:bg-destructive/10 hover:text-destructive",
                isDeleting && "cursor-not-allowed opacity-100"
              )}
              title="Remove enrichment"
            >
              {isDeleting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <X className="h-3.5 w-3.5" />
              )}
            </button>
          )}
        </div>

        {/* Line 2: Full URL */}
        <p className="truncate text-xs text-muted-foreground">
          {page.url}
        </p>

        {/* Line 3+: Content body (markdown) */}
        {page.content && (
          <div className="prose-compact mt-1 line-clamp-2 text-xs text-muted-foreground/80 [&_*]:m-0 [&_*]:text-xs [&_a]:text-muted-foreground/80 [&_a]:no-underline [&_code]:bg-transparent [&_code]:p-0 [&_h1]:text-xs [&_h2]:text-xs [&_h3]:text-xs [&_p]:inline">
            <ReactMarkdown key={`web-page-${encodeURIComponent(page.url)}`} remarkPlugins={[remarkGfm]}>
              {page.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
