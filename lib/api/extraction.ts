/**
 * HTML content extraction and analysis utilities.
 *
 * These functions help identify and preview CSS selectors for content
 * filtering, used by the AI assistant to suggest extraction rules.
 *
 * @module lib/api/extraction
 */

import * as cheerio from "cheerio";
import type { Element } from "domhandler";

/** A candidate CSS selector found in the HTML. */
export interface SelectorCandidate {
  /** The CSS selector string (e.g., "#main", ".article-content"). */
  selector: string;
  /** The HTML tag name of the matched element. */
  tagName: string;
  /** Text content preview for context. */
  context: string;
  /** Parent element's selector if available. */
  parentSelector?: string;
}

/** Result of searching for elements by text content. */
export interface FindElementResult {
  /** The original search text. */
  searchText: string;
  /** List of matching selector candidates. */
  results: SelectorCandidate[];
  /** Total number of matches found (before deduplication). */
  totalFound: number;
}

/** Result of previewing a CSS exclusion rule. */
export interface PreviewExclusionResult {
  /** The CSS selector being tested. */
  selector: string;
  /** Number of elements matched by the selector. */
  matchCount: number;
  /** Text previews of content that would be removed. */
  removedPreviews: string[];
  /** Preview of remaining text after exclusion. */
  remainingPreview: string;
  /** Full remaining HTML after exclusion. */
  remainingHtml: string;
  /** Original HTML length in characters. */
  originalLength: number;
  /** Combined selector including existing feed rules. */
  combinedSelector?: string;
  /** Number of existing feed rules applied. */
  existingRulesCount?: number;
}

/**
 * Searches HTML for elements containing specified text and returns CSS selector candidates.
 *
 * Used by the AI assistant to help users identify elements to exclude from
 * article content. Searches through the DOM hierarchy and generates various
 * selector types (ID, class, data attributes, tag+class combinations).
 *
 * @param html - The HTML content to search
 * @param searchText - Text to find within element content
 * @returns Search results with selector candidates
 */
export function findElementByText(
  html: string,
  searchText: string
): FindElementResult {
  const $ = cheerio.load(html);
  const results: SelectorCandidate[] = [];
  const searchLower = searchText.toLowerCase();

  // Find elements containing the search text (including in child elements)
  $("*")
    .filter(function () {
      // Get all text content including children
      const fullText = $(this).text().toLowerCase();
      if (!fullText.includes(searchLower)) return false;

      // Check if this element or any direct child contains the text
      // (to avoid matching too high in the hierarchy)
      const directText = $(this).clone().children().remove().end().text().toLowerCase();
      if (directText.includes(searchLower)) return true;

      // Check immediate children
      const childrenWithText = $(this).children().filter(function () {
        return $(this).text().toLowerCase().includes(searchLower);
      });
      return childrenWithText.length > 0 && childrenWithText.length <= 3;
    })
    .each(function () {
      const el = $(this);
      const tagName = (this as Element).tagName?.toLowerCase() || "";

      // Skip common wrapper elements
      if (["html", "body", "head"].includes(tagName)) return;

      // Build selector candidates
      const selectors: string[] = [];

      // By ID
      const id = el.attr("id");
      if (id) selectors.push(`#${id}`);

      // By class
      const classes = el.attr("class");
      if (classes) {
        const classList = classes.split(/\s+/).filter(Boolean);
        if (classList.length > 0) {
          selectors.push(`.${classList.join(".")}`);
        }
      }

      // By data attribute
      const dataAttrs = Object.keys((this as Element).attribs || {}).filter(
        (k) => k.startsWith("data-")
      );
      for (const attr of dataAttrs.slice(0, 2)) {
        const val = el.attr(attr);
        if (val) selectors.push(`[${attr}="${val}"]`);
      }

      // By tag + class combination
      if (classes) {
        const firstClass = classes.split(/\s+/)[0];
        if (firstClass) selectors.push(`${tagName}.${firstClass}`);
      }

      // Get context (surrounding text)
      const text = el.text().trim();
      const context =
        text.length > 100 ? text.substring(0, 100) + "..." : text;

      // Get parent selector for context
      const parent = el.parent();
      let parentSelector: string | undefined;
      if (parent.length) {
        const parentId = parent.attr("id");
        const parentClass = parent.attr("class")?.split(/\s+/)[0];
        if (parentId) parentSelector = `#${parentId}`;
        else if (parentClass) parentSelector = `.${parentClass}`;
      }

      for (const selector of selectors.slice(0, 3)) {
        results.push({
          selector,
          tagName,
          context,
          parentSelector,
        });
      }
    });

  // Deduplicate and limit results
  const uniqueResults = results
    .filter(
      (r, i, arr) => arr.findIndex((x) => x.selector === r.selector) === i
    )
    .slice(0, 10);

  return {
    searchText,
    results: uniqueResults,
    totalFound: results.length,
  };
}

/**
 * Previews the effect of applying a CSS selector exclusion rule to HTML.
 *
 * Shows what content would be removed by a selector and what would remain.
 * Applies existing feed rules first, then shows the effect of the new rule.
 *
 * @param html - The HTML content to preview
 * @param selector - The new CSS selector to test
 * @param existingSelectors - Existing CSS selectors from feed extraction rules
 * @returns Preview result with removed/remaining content
 */
export function previewExclusion(
  html: string,
  selector: string,
  existingSelectors: string[] = []
): PreviewExclusionResult {
  const $ = cheerio.load(html);

  // First, apply existing rules (to show current state with existing rules)
  for (const existingSelector of existingSelectors) {
    $(existingSelector).remove();
  }

  // Now count and get preview of elements matching the NEW selector
  const matchedElements = $(selector);
  const matchCount = matchedElements.length;

  // Get preview of what will be removed by the new rule
  const removedPreviews: string[] = [];
  matchedElements.each(function () {
    const text = $(this).text().trim();
    if (text) {
      removedPreviews.push(
        text.length > 200 ? text.substring(0, 200) + "..." : text
      );
    }
  });

  // Remove elements matching the new selector
  matchedElements.remove();

  // Get remaining HTML content (after all rules applied)
  const remainingHtml = $("body").html() || "";

  // Get remaining text content (simplified preview)
  const remainingText = $("body").text().trim();
  const previewLength = 500;
  const remainingPreview =
    remainingText.length > previewLength
      ? remainingText.substring(0, previewLength) + "..."
      : remainingText;

  // Build combined selector for display
  const allSelectors = [...existingSelectors, selector];
  const combinedSelector = allSelectors.join(", ");

  return {
    selector,
    matchCount,
    removedPreviews: removedPreviews.slice(0, 5),
    remainingPreview,
    remainingHtml,
    originalLength: html.length,
    combinedSelector: existingSelectors.length > 0 ? combinedSelector : undefined,
    existingRulesCount: existingSelectors.length > 0 ? existingSelectors.length : undefined,
  };
}
