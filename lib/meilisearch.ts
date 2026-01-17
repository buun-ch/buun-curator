/**
 * Meilisearch search client for Next.js.
 *
 * This module provides search-only functionality.
 * Index management is handled by the Worker (SearchReindexWorkflow).
 *
 * @module lib/meilisearch
 */

import { MeiliSearch } from "meilisearch";

const MEILISEARCH_HOST = process.env.MEILISEARCH_HOST;
const MEILISEARCH_API_KEY = process.env.MEILISEARCH_API_KEY;
const MEILISEARCH_INDEX = process.env.MEILISEARCH_INDEX || "buun-curator";

/**
 * Returns whether Meilisearch is configured.
 */
export function isMeilisearchEnabled(): boolean {
  return Boolean(MEILISEARCH_HOST && MEILISEARCH_API_KEY);
}

/**
 * Creates a Meilisearch client instance.
 *
 * @throws Error if Meilisearch is not configured
 */
function getMeilisearchClient(): MeiliSearch {
  if (!MEILISEARCH_HOST || !MEILISEARCH_API_KEY) {
    throw new Error(
      "Meilisearch not configured. Set MEILISEARCH_HOST and MEILISEARCH_API_KEY."
    );
  }

  // Add protocol if not present
  const host = MEILISEARCH_HOST.startsWith("http")
    ? MEILISEARCH_HOST
    : `http://${MEILISEARCH_HOST}`;

  return new MeiliSearch({
    host,
    apiKey: MEILISEARCH_API_KEY,
  });
}

/** Search result entry from Meilisearch. */
interface SearchHit {
  id: string;
  feedId: string;
  title: string;
  summary: string;
  author: string | null;
  publishedAt: number | null;
  createdAt: number;
  _formatted?: {
    title?: string;
    summary?: string;
  };
}

/** Search response. */
export interface SearchResponse {
  hits: SearchHit[];
  estimatedTotalHits: number;
  processingTimeMs: number;
}

/**
 * Searches entries in the Meilisearch index.
 *
 * @param query - Search query string
 * @param options - Search options
 * @returns Search results
 */
export async function searchEntries(
  query: string,
  options: {
    feedId?: string;
    limit?: number;
    offset?: number;
  } = {}
): Promise<SearchResponse> {
  const client = getMeilisearchClient();
  const index = client.index(MEILISEARCH_INDEX);

  // Build filter array
  const filters: string[] = [];

  if (options.feedId) {
    filters.push(`feedId = "${options.feedId}"`);
  }

  const result = await index.search(query, {
    filter: filters.length > 0 ? filters.join(" AND ") : undefined,
    limit: options.limit ?? 20,
    offset: options.offset ?? 0,
    attributesToHighlight: ["title", "summary"],
    highlightPreTag: "<mark>",
    highlightPostTag: "</mark>",
    sort: ["publishedAt:desc"],
  });

  return {
    hits: result.hits as SearchHit[],
    estimatedTotalHits: result.estimatedTotalHits ?? 0,
    processingTimeMs: result.processingTimeMs ?? 0,
  };
}
