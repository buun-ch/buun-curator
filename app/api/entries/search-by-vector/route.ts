import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { sql } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:search-by-vector");

const DEFAULT_THRESHOLD = 0.8;
const DEFAULT_LIMIT = 10;
const MAX_LIMIT = 50;
const EMBEDDING_DIM = 768;

/**
 * POST /api/entries/search-by-vector - Search entries by embedding vector similarity.
 *
 * Authentication is handled by middleware via INTERNAL_API_TOKEN.
 *
 * Body:
 * - embedding: number[] (768-dimensional vector)
 * - limit?: number (default: 10, max: 50)
 * - threshold?: number (default: 0.8, max cosine distance)
 *
 * Response:
 * - entries: Array of matching entries with similarity scores
 * - totalCount: Total number of matches within threshold
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { embedding, limit: rawLimit, threshold: rawThreshold } = body;

    // Validate embedding
    if (!embedding || !Array.isArray(embedding)) {
      return NextResponse.json(
        { error: "embedding is required and must be an array" },
        { status: 400 },
      );
    }

    if (embedding.length !== EMBEDDING_DIM) {
      return NextResponse.json(
        { error: `embedding must be ${EMBEDDING_DIM}-dimensional` },
        { status: 400 },
      );
    }

    // Validate and clamp parameters
    const threshold = Math.min(
      Math.max(
        typeof rawThreshold === "number" ? rawThreshold : DEFAULT_THRESHOLD,
        0,
      ),
      2,
    );
    const limit = Math.min(
      Math.max(typeof rawLimit === "number" ? rawLimit : DEFAULT_LIMIT, 1),
      MAX_LIMIT,
    );

    // Format embedding for pgvector
    const vectorStr = `[${embedding.join(",")}]`;

    // Query similar entries using cosine distance
    const result = await db.execute<{
      id: string;
      feed_id: string;
      feed_name: string | null;
      title: string;
      url: string;
      summary: string | null;
      author: string | null;
      thumbnail_url: string | null;
      published_at: Date | null;
      created_at: Date;
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
        e.author,
        e.thumbnail_url,
        e.published_at,
        e.created_at,
        (e.embedding <=> '${vectorStr}'::vector) as similarity_score
      FROM entries e
      LEFT JOIN feeds f ON e.feed_id = f.id
      WHERE e.embedding IS NOT NULL
        AND (e.embedding <=> '${vectorStr}'::vector) < ${threshold}
      ORDER BY similarity_score ASC
      LIMIT ${limit}
    `),
    );

    // Get total count within threshold
    const countResult = await db.execute<{ count: string }>(
      sql.raw(`
      SELECT COUNT(*) as count
      FROM entries
      WHERE embedding IS NOT NULL
        AND (embedding <=> '${vectorStr}'::vector) < ${threshold}
    `),
    );
    const totalCount = Number(countResult.rows[0]?.count || 0);

    // Transform results to camelCase
    const matchedEntries = result.rows.map((row) => ({
      id: row.id,
      feedId: row.feed_id,
      feedName: row.feed_name,
      title: row.title,
      url: row.url,
      summary: row.summary,
      author: row.author,
      thumbnailUrl: row.thumbnail_url,
      publishedAt: row.published_at,
      createdAt: row.created_at,
      similarityScore: row.similarity_score,
    }));

    log.info(
      { limit, threshold, resultCount: matchedEntries.length, totalCount },
      "vector search completed",
    );

    return NextResponse.json({
      entries: matchedEntries,
      totalCount,
    });
  } catch (error) {
    log.error({ error }, "failed to search entries by vector");
    return NextResponse.json(
      { error: "Failed to search entries" },
      { status: 500 },
    );
  }
}
