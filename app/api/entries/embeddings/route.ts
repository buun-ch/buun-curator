import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries } from "@/db/schema";
import { eq, sql, isNull, and, gt } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:embeddings");

interface EmbeddingData {
  entryId: string;
  embedding: number[];
}

/**
 * GET /api/entries/embeddings - Get entries that need embeddings.
 *
 * Returns entries that have content (filteredContent or summary) but no embedding.
 * Supports cursor-based pagination via `after` parameter.
 *
 * Query params:
 *   - first: number (default 100, max 500)
 *   - after: string (cursor for pagination, entry id)
 */
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const first = Math.min(parseInt(searchParams.get("first") || "100"), 500);
    const after = searchParams.get("after");

    // Entries that have content but no embedding
    const conditions = [
      isNull(entries.embedding),
      sql`(${entries.filteredContent} IS NOT NULL AND ${entries.filteredContent} != ''
           OR ${entries.summary} IS NOT NULL AND ${entries.summary} != '')`,
    ];

    if (after) {
      conditions.push(gt(entries.id, after));
    }

    // Get total count (without cursor)
    const countResult = await db
      .select({ count: sql<number>`count(*)` })
      .from(entries)
      .where(
        and(
          isNull(entries.embedding),
          sql`(${entries.filteredContent} IS NOT NULL AND ${entries.filteredContent} != ''
               OR ${entries.summary} IS NOT NULL AND ${entries.summary} != '')`
        )
      );
    const totalCount = Number(countResult[0]?.count || 0);

    // Fetch entries
    const result = await db
      .select({ id: entries.id })
      .from(entries)
      .where(and(...conditions))
      .orderBy(entries.id)
      .limit(first + 1);

    const hasMore = result.length > first;
    const entryIds = result.slice(0, first).map((r) => r.id);
    const endCursor = entryIds.length > 0 ? entryIds[entryIds.length - 1] : null;

    return NextResponse.json({
      entryIds,
      totalCount,
      hasMore,
      endCursor,
    });
  } catch (error) {
    log.error({ error }, "failed to get entries for embedding");
    return NextResponse.json(
      { error: "Failed to get entries for embedding" },
      { status: 500 }
    );
  }
}

/**
 * POST /api/entries/embeddings - Save embeddings for entries.
 *
 * Body: { embeddings: [{ entryId: string, embedding: number[] }, ...] }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { embeddings } = body as { embeddings: EmbeddingData[] };

    if (!Array.isArray(embeddings) || embeddings.length === 0) {
      return NextResponse.json(
        { error: "embeddings must be a non-empty array" },
        { status: 400 }
      );
    }

    // Validate all entries have required fields
    for (const item of embeddings) {
      if (typeof item.entryId !== "string" || !Array.isArray(item.embedding)) {
        return NextResponse.json(
          { error: "Each embedding must have entryId (string) and embedding (number[])" },
          { status: 400 }
        );
      }
      if (item.embedding.length !== 768) {
        return NextResponse.json(
          { error: `Embedding must be 768 dimensions, got ${item.embedding.length}` },
          { status: 400 }
        );
      }
    }

    // Update embeddings one by one (drizzle doesn't support bulk update with different values)
    let updatedCount = 0;
    for (const item of embeddings) {
      const result = await db
        .update(entries)
        .set({ embedding: item.embedding })
        .where(eq(entries.id, item.entryId));

      if (result.rowCount && result.rowCount > 0) {
        updatedCount++;
      }
    }

    log.info({ count: embeddings.length, updatedCount }, "saved embeddings");

    return NextResponse.json({ updatedCount });
  } catch (error) {
    log.error({ error }, "failed to save embeddings");
    return NextResponse.json(
      { error: "Failed to save embeddings" },
      { status: 500 }
    );
  }
}
