import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, feeds } from "@/db/schema";
import { eq, inArray } from "drizzle-orm";
import { createLogger } from "@/lib/logger";
import { isMeilisearchEnabled, searchEntries } from "@/lib/meilisearch";

const log = createLogger("api:search");

/**
 * GET /api/search - Search entries using Meilisearch.
 *
 * Query parameters:
 * - q: Search query (required)
 * - feedId: Filter by feed ID
 * - limit: Number of results (default: 20, max: 100)
 * - offset: Pagination offset
 */
export async function GET(request: NextRequest) {
  try {
    if (!isMeilisearchEnabled()) {
      return NextResponse.json(
        { error: "Search is not configured" },
        { status: 503 }
      );
    }

    const searchParams = request.nextUrl.searchParams;
    const query = searchParams.get("q");

    if (!query || query.trim() === "") {
      return NextResponse.json(
        { error: "Search query is required" },
        { status: 400 }
      );
    }

    const feedId = searchParams.get("feedId") ?? undefined;
    const limit = Math.min(parseInt(searchParams.get("limit") || "20"), 100);
    const offset = parseInt(searchParams.get("offset") || "0");

    const result = await searchEntries(query, {
      feedId,
      limit,
      offset,
    });

    // Fetch current isRead/isStarred status from DB
    const entryIds = result.hits.map((hit) => hit.id);
    const feedIds = [...new Set(result.hits.map((hit) => hit.feedId))];
    const statusMap = new Map<string, { isRead: boolean; isStarred: boolean }>();
    const feedNameMap = new Map<string, string>();

    if (entryIds.length > 0) {
      const [dbEntries, dbFeeds] = await Promise.all([
        db
          .select({
            id: entries.id,
            isRead: entries.isRead,
            isStarred: entries.isStarred,
          })
          .from(entries)
          .where(inArray(entries.id, entryIds)),
        db
          .select({
            id: feeds.id,
            name: feeds.name,
          })
          .from(feeds)
          .where(inArray(feeds.id, feedIds)),
      ]);

      for (const entry of dbEntries) {
        statusMap.set(entry.id, {
          isRead: entry.isRead,
          isStarred: entry.isStarred,
        });
      }

      for (const feed of dbFeeds) {
        feedNameMap.set(feed.id, feed.name);
      }
    }

    // Transform to match entries API format for frontend compatibility
    const responseEntries = result.hits.map((hit) => {
      const status = statusMap.get(hit.id);
      return {
        id: hit.id,
        feedId: hit.feedId,
        feedName: feedNameMap.get(hit.feedId),
        title: hit.title,
        summary: hit.summary,
        author: hit.author,
        publishedAt: hit.publishedAt
          ? new Date(hit.publishedAt * 1000).toISOString()
          : null,
        isRead: status?.isRead ?? false,
        isStarred: status?.isStarred ?? false,
        createdAt: new Date(hit.createdAt * 1000).toISOString(),
        // Highlighted versions for UI
        _highlighted: {
          title: hit._formatted?.title,
          summary: hit._formatted?.summary,
        },
      };
    });

    return NextResponse.json({
      entries: responseEntries,
      totalCount: result.estimatedTotalHits,
      processingTimeMs: result.processingTimeMs,
      query,
    });
  } catch (error) {
    log.error({ error }, "Search failed");
    return NextResponse.json({ error: "Search failed" }, { status: 500 });
  }
}
