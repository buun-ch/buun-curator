import { eq, sql } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";

import { db } from "@/db";
import { entries } from "@/db/schema";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:related");

interface RouteParams {
  params: Promise<{ id: string }>;
}

const DEFAULT_THRESHOLD = 0.5;
const DEFAULT_LIMIT = 5;
const MAX_LIMIT = 10;

/**
 * GET /api/entries/[id]/related - Get related entries using embedding similarity.
 *
 * Query params:
 * - threshold: Maximum cosine distance (default: 0.5)
 * - limit: Maximum number of results (default: 5, max: 10)
 */
export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;
    const { searchParams } = new URL(request.url);

    const threshold = Math.min(
      Math.max(
        parseFloat(searchParams.get("threshold") || "") || DEFAULT_THRESHOLD,
        0,
      ),
      2,
    );
    const limit = Math.min(
      Math.max(parseInt(searchParams.get("limit") || "") || DEFAULT_LIMIT, 1),
      MAX_LIMIT,
    );

    // Fetch the source entry's embedding
    const [sourceEntry] = await db
      .select({
        id: entries.id,
        embedding: entries.embedding,
      })
      .from(entries)
      .where(eq(entries.id, entryId));

    if (!sourceEntry) {
      return NextResponse.json({ error: "Entry not found" }, { status: 404 });
    }

    // If source entry has no embedding, return empty result
    if (!sourceEntry.embedding) {
      return NextResponse.json({ entries: [] });
    }

    // Format embedding for pgvector
    const vectorStr = `[${sourceEntry.embedding.join(",")}]`;

    // Query similar entries using cosine distance
    const result = await db.execute<{
      id: string;
      feed_id: string;
      feed_name: string | null;
      title: string;
      url: string;
      summary: string;
      thumbnail_url: string | null;
      published_at: Date | null;
      similarity_score: number;
    }>(
      sql.raw(`
      SELECT
        e.id,
        e.feed_id,
        f.name as feed_name,
        e.title,
        e.url,
        e.summary,
        e.thumbnail_url,
        e.published_at,
        (e.embedding <=> '${vectorStr}'::vector) as similarity_score
      FROM entries e
      LEFT JOIN feeds f ON e.feed_id = f.id
      WHERE e.id != '${entryId}'
        AND e.embedding IS NOT NULL
        AND (e.embedding <=> '${vectorStr}'::vector) < ${threshold}
      ORDER BY similarity_score ASC
      LIMIT ${limit}
    `),
    );

    // Transform results to camelCase
    const relatedEntries = result.rows.map((row) => ({
      id: row.id,
      feedId: row.feed_id,
      feedName: row.feed_name,
      title: row.title,
      url: row.url,
      summary: row.summary,
      thumbnailUrl: row.thumbnail_url,
      publishedAt: row.published_at,
      similarityScore: row.similarity_score,
    }));

    return NextResponse.json({ entries: relatedEntries });
  } catch (error) {
    log.error({ error }, "failed to fetch related entries");
    return NextResponse.json(
      { error: "Failed to fetch related entries" },
      { status: 500 },
    );
  }
}
