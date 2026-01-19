"use client";

import {
  useState,
  useCallback,
  useImperativeHandle,
  forwardRef,
  useRef,
} from "react";
import type { Ref } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChevronDown, ChevronUp, FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

import type { ContentViewerProps, ContentViewerRef } from "./types";
import { useContent } from "./hooks/use-content";
import { ViewerToolbar } from "./viewer-toolbar";
import { EntryHeader } from "./entry-header";
import { LanguageToggle } from "./language-toggle";
import { EntryContent } from "./entry-content";
import { DebugPanel } from "./debug-panel";
import { RelatedEntriesSection } from "./related-entries-section";
import { AnnotationSection } from "./annotation-section";
import { markdownComponents } from "./markdown-components";

// Re-export types for external use
export type { ContentViewerProps, ContentViewerRef } from "./types";

/**
 * Content viewer component for displaying entry details.
 *
 * Supports navigation, starring, read status, and language switching.
 */
export const ContentViewer = forwardRef(function ContentViewer(
  {
    entry,
    loading = false,
    onToggleStar,
    onToggleKeep,
    onToggleRead,
    onRefresh,
    refreshing = false,
    onPrevious,
    onNext,
    hasPrevious = false,
    hasNext = false,
    languageMode,
    onLanguageModeChange,
    isTranslating = false,
    onRetranslate,
    contextPanelOpen = false,
    onContextPanelOpenChange,
    onSelectEntry,
    onUpdateAnnotation,
  }: ContentViewerProps,
  ref: Ref<ContentViewerRef>
) {
  // Ref to the scrollable content container
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Expose scroll methods via ref
  useImperativeHandle(
    ref,
    () => ({
      scrollBy: (amount: number) => {
        // Use "instant" to allow smooth continuous scrolling when key is held
        scrollContainerRef.current?.scrollBy({
          top: amount,
          behavior: "instant",
        });
      },
      scrollToTop: () => {
        scrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
      },
      scrollToBottom: () => {
        const el = scrollContainerRef.current;
        if (el) {
          el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
        }
      },
    }),
    []
  );

  // Content determination hook
  const { content, isMarkdown, processedHtmlContent, hasTranslation } =
    useContent(entry);

  // Track scroll position to show/hide header border
  const [isScrolled, setIsScrolled] = useState(false);
  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setIsScrolled(e.currentTarget.scrollTop > 0);
  }, []);

  // Scroll button handlers
  const handleScrollToTop = useCallback(() => {
    scrollContainerRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const handleScrollToBottom = useCallback(() => {
    const el = scrollContainerRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, []);

  // Handle annotation update
  const handleAnnotationUpdate = useCallback(
    async (annotation: string) => {
      if (entry && onUpdateAnnotation) {
        await onUpdateAnnotation(entry.id, annotation);
      }
    },
    [entry, onUpdateAnnotation]
  );

  if (!entry) {
    return (
      <div className="flex h-full flex-col items-center justify-center bg-background">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FileText className="h-5 w-5" />
            </EmptyMedia>
            <EmptyTitle>No Entry Selected</EmptyTitle>
            <EmptyDescription>
              Choose an entry from the list to read.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header / Toolbar */}
      <ViewerToolbar
        entry={entry}
        isScrolled={isScrolled}
        refreshing={refreshing}
        contextPanelOpen={contextPanelOpen}
        hasPrevious={hasPrevious}
        hasNext={hasNext}
        onPrevious={onPrevious}
        onNext={onNext}
        onToggleRead={onToggleRead}
        onToggleStar={onToggleStar}
        onToggleKeep={onToggleKeep}
        onRefresh={onRefresh}
        onContextPanelOpenChange={onContextPanelOpenChange}
      />

      {/* Entry content */}
      <div className="relative flex-1 overflow-hidden">
        {/* Scrollable content */}
        <div
          ref={scrollContainerRef}
          className="absolute inset-0 overflow-auto"
          onScroll={handleScroll}
        >
          {loading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="size-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <article className="px-[clamp(1rem,8%,5rem)] py-8">
              {/* Entry header */}
              <EntryHeader entry={entry} />

              {/* YouTube embed (if available) */}
              {entry.youtubeVideoId && (
                <div className="mb-8">
                  <div className="relative w-full overflow-hidden rounded-lg pt-[56.25%]">
                    <iframe
                      className="absolute inset-0 h-full w-full"
                      src={`https://www.youtube.com/embed/${entry.youtubeVideoId}`}
                      title={entry.title}
                      allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                      allowFullScreen
                    />
                  </div>
                </div>
              )}

              {/* Summary (if available) */}
              {entry.summary && (
                <div className="mb-8 rounded-lg border bg-muted/50 p-4">
                  <div className="prose prose-sm prose-neutral dark:prose-invert max-w-none">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      components={markdownComponents}
                    >
                      {entry.summary}
                    </ReactMarkdown>
                  </div>
                </div>
              )}

              {/* Language toggle */}
              <LanguageToggle
                value={languageMode}
                onChange={onLanguageModeChange}
              />

              {/* Entry body */}
              <EntryContent
                entry={entry}
                languageMode={languageMode}
                content={content}
                isMarkdown={isMarkdown}
                processedHtmlContent={processedHtmlContent}
                hasTranslation={hasTranslation}
                isTranslating={isTranslating}
                onRetranslate={onRetranslate}
              />

              {/* Related Entries */}
              <RelatedEntriesSection
                entryId={entry.id}
                onEntryClick={(entryId) => onSelectEntry?.({ id: entryId })}
              />

              {/* Annotation */}
              <AnnotationSection
                entry={entry}
                onUpdate={onUpdateAnnotation ? handleAnnotationUpdate : undefined}
              />

              {/* Debug Panel */}
              <DebugPanel entry={entry} />
            </article>
          )}
        </div>

        {/* Floating scroll buttons - positioned relative to viewport */}
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-end pr-6">
          <div className="pointer-events-auto flex flex-col gap-1">
            <Button
              variant="outline"
              size="icon"
              className="size-8 rounded-full bg-background/80 shadow-sm backdrop-blur-sm"
              onClick={handleScrollToTop}
              title="Scroll to top (gg)"
            >
              <ChevronUp className="size-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="size-8 rounded-full bg-background/80 shadow-sm backdrop-blur-sm"
              onClick={handleScrollToBottom}
              title="Scroll to bottom (G)"
            >
              <ChevronDown className="size-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
});
