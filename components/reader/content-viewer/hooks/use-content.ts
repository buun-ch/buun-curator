import { useMemo } from "react";

import type { Entry } from "@/lib/types";

interface UseContentResult {
  /** The content to display. */
  content: string;
  /** Whether the content is Markdown (true) or HTML (false). */
  isMarkdown: boolean;
  /** Processed HTML content with target="_blank" added to links. */
  processedHtmlContent: string;
  /** Whether the entry has translation content. */
  hasTranslation: boolean;
}

/**
 * Hook for determining entry content and format.
 *
 * @param entry - The entry to extract content from
 * @returns Content string, format flag, and processed HTML
 */
export function useContent(entry?: Entry | null): UseContentResult {
  // Check if entry has translation content (non-empty string)
  const hasTranslation = Boolean(
    entry?.translatedContent && entry.translatedContent.length > 0
  );

  // Determine content and format
  const { content, isMarkdown } = useMemo(() => {
    // If feedContent is long enough (>=1000 chars), prefer it over fullContent
    const feedContent = entry?.feedContent;
    if (feedContent && feedContent.length >= 1000) {
      return { content: feedContent, isMarkdown: false };
    }
    const filteredContent = entry?.filteredContent;
    if (filteredContent && filteredContent.length > 0) {
      return { content: filteredContent, isMarkdown: true };
    }
    const fullContent = entry?.fullContent;
    if (fullContent && fullContent.length > 0) {
      return { content: fullContent, isMarkdown: true };
    }
    // Fall back to feedContent (HTML)
    return { content: feedContent || "", isMarkdown: false };
  }, [entry?.fullContent, entry?.filteredContent, entry?.feedContent]);

  // Process HTML content to add target="_blank" to all links
  const processedHtmlContent = useMemo(() => {
    if (isMarkdown || !content) return content;
    // Add target="_blank" and rel="noopener noreferrer" to all <a> tags
    return content.replace(
      /<a\s+([^>]*?)href=/gi,
      '<a $1target="_blank" rel="noopener noreferrer" href='
    );
  }, [content, isMarkdown]);

  return {
    content,
    isMarkdown,
    processedHtmlContent,
    hasTranslation,
  };
}
