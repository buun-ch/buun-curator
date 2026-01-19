"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Loader2, RefreshCw } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { Entry, LanguageMode } from "@/lib/types";

import { markdownComponents } from "./markdown-components";

interface EntryContentProps {
  entry: Entry;
  languageMode: LanguageMode;
  content: string;
  isMarkdown: boolean;
  processedHtmlContent: string;
  hasTranslation: boolean;
  isTranslating: boolean;
  onRetranslate?: () => void;
}

/**
 * Entry content component.
 *
 * Renders entry body based on language mode (original, translated, or both).
 */
export function EntryContent({
  entry,
  languageMode,
  content,
  isMarkdown,
  processedHtmlContent,
  hasTranslation,
  isTranslating,
  onRetranslate,
}: EntryContentProps) {
  // Original or both mode: show original content
  if (languageMode === "original" || languageMode === "both") {
    if (!content) {
      return (
        <div className="text-center text-muted-foreground">
          <p>No content available.</p>
          <Button
            variant="link"
            className="mt-2"
            onClick={() => window.open(entry.url, "_blank")}
          >
            Read original entry
          </Button>
        </div>
      );
    }

    if (isMarkdown) {
      return (
        <div className="prose max-w-none prose-neutral dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {content}
          </ReactMarkdown>
        </div>
      );
    }

    return (
      <div
        className="prose max-w-none prose-neutral dark:prose-invert"
        dangerouslySetInnerHTML={{ __html: processedHtmlContent }}
      />
    );
  }

  // Translated mode
  if (languageMode === "translated") {
    if (hasTranslation) {
      return (
        <div className="relative">
          <Button
            variant="ghost"
            size="icon"
            className="absolute -top-8 right-0 size-7"
            onClick={onRetranslate}
            disabled={isTranslating}
            title="Re-translate"
          >
            <RefreshCw
              className={cn("size-3.5", isTranslating && "animate-spin")}
            />
          </Button>
          <div className="prose max-w-none prose-neutral dark:prose-invert">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {entry.translatedContent}
            </ReactMarkdown>
          </div>
        </div>
      );
    }

    if (isTranslating) {
      return (
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <Loader2 className="mb-2 size-6 animate-spin" />
          <p>Translating...</p>
        </div>
      );
    }

    return (
      <div className="py-8 text-center text-muted-foreground">
        <p>Translation not available.</p>
      </div>
    );
  }

  return null;
}
