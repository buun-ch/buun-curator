"use client";

import * as React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Languages, RefreshCw, Loader2, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

// Custom components for ReactMarkdown
const markdownComponents = {
  a: ({
    href,
    children,
    ...props
  }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" {...props}>
        {children}
      </a>
    );
  },
  img: ({ src, alt, ...props }: React.ImgHTMLAttributes<HTMLImageElement>) => {
    if (!src) return null;
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={src} alt={alt || ""} {...props} />;
  },
};

interface TranslationPanelProps {
  /** Translated content in Markdown format. */
  translatedContent?: string | null;
  /** Whether translation is in progress. */
  isTranslating: boolean;
  /** Callback to trigger re-translation. */
  onRetranslate: () => void;
  /** Callback to close the panel (switch back to original mode). */
  onClose: () => void;
}

/**
 * Panel for displaying translated content alongside the original.
 * Shown when languageMode is "both".
 */
export function TranslationPanel({
  translatedContent,
  isTranslating,
  onRetranslate,
  onClose,
}: TranslationPanelProps) {
  const hasTranslation = Boolean(
    translatedContent && translatedContent.length > 0,
  );

  return (
    <div className="flex h-full flex-col border-l bg-background">
      {/* Header */}
      <div className="flex h-11 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Languages className="size-4" />
          <span>Translation</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={onRetranslate}
            disabled={isTranslating}
            title="Re-translate"
          >
            <RefreshCw
              className={cn("size-3.5", isTranslating && "animate-spin")}
            />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="size-7"
            onClick={onClose}
            title="Close translation panel"
          >
            <X className="size-3.5" />
          </Button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto px-4 py-6">
        {hasTranslation ? (
          <div className="prose max-w-none prose-neutral dark:prose-invert">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {translatedContent!}
            </ReactMarkdown>
          </div>
        ) : isTranslating ? (
          <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="mb-2 size-6 animate-spin" />
            <p>Translating...</p>
          </div>
        ) : (
          <div className="py-8 text-center text-muted-foreground">
            <p>Translation not available.</p>
            <Button variant="link" className="mt-2" onClick={onRetranslate}>
              Start translation
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
