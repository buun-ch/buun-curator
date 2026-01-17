import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, feeds } from "@/db/schema";
import { eq, desc, asc, and, sql, isNull, isNotNull } from "drizzle-orm";
import { createEntry, isError } from "@/lib/api";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries");

type SortMode = "newest" | "oldest" | "recommended";

/**
 * Compute the average embedding vector from keep=true entries.
 * Returns null if no keep vectors exist.
 */
async function getKeepVector(): Promise<number[] | null> {
  const result = await db.execute<{ avg_embedding: string | null }>(sql`
    SELECT AVG(embedding)::text as avg_embedding
    FROM entries
    WHERE keep = true AND embedding IS NOT NULL
  `);

  const avgEmbedding = result.rows[0]?.avg_embedding;
  if (!avgEmbedding) return null;

  // Parse the vector string "[0.1,0.2,...]" format
  const match = avgEmbedding.match(/\[(.*)\]/);
  if (!match) return null;

  return match[1].split(",").map(Number);
}

// Cursor format for recommended sort: { score: string (fixed precision), id: string }
interface RecommendedCursor {
  score: string; // Stored as string to preserve precision
  id: string;
}

// Use 15 decimal places to avoid floating-point precision issues
const SCORE_PRECISION = 15;

function encodeRecommendedCursor(score: number, id: string): string {
  // Store score as fixed-precision string to avoid JSON floating-point issues
  const cursor: RecommendedCursor = { score: score.toFixed(SCORE_PRECISION), id };
  return Buffer.from(JSON.stringify(cursor)).toString("base64url");
}

function decodeRecommendedCursor(cursor: string): RecommendedCursor | null {
  try {
    const decoded = Buffer.from(cursor, "base64url").toString("utf-8");
    return JSON.parse(decoded) as RecommendedCursor;
  } catch {
    return null;
  }
}

interface RecommendedSortParams {
  feedId: string | null;
  categoryId: string | null;
  unreadOnly: boolean;
  starredOnly: boolean;
  hasSummary: boolean | undefined;
  graphAdded: boolean | undefined;
  first: number;
  after: string | null;
  preserveIds: string[];
}

/** Result row type for recommended sort queries. */
interface RecommendedResultRow {
  [key: string]: unknown;
  id: string;
  feed_id: string;
  feed_name: string | null;
  title: string;
  url: string;
  summary: string;
  author: string | null;
  published_at: Date | null;
  is_read: boolean;
  is_starred: boolean;
  keep: boolean;
  thumbnail_url: string | null;
  metadata: unknown;
  created_at: Date;
  similarity_score: number;
}

/** Converts a result row to an edge node. */
function rowToNode(row: RecommendedResultRow) {
  return {
    id: row.id,
    feedId: row.feed_id,
    feedName: row.feed_name,
    title: row.title,
    url: row.url,
    summary: row.summary,
    author: row.author,
    publishedAt: row.published_at,
    isRead: row.is_read,
    isStarred: row.is_starred,
    keep: row.keep,
    thumbnailUrl: row.thumbnail_url,
    metadata: row.metadata,
    createdAt: row.created_at,
    similarityScore: row.similarity_score,
  };
}

/**
 * Handle recommended sort using embedding similarity.
 * Sorts entries by cosine similarity to the average embedding of keep=true entries.
 */
async function handleRecommendedSort(
  _request: NextRequest,
  params: RecommendedSortParams
): Promise<NextResponse> {
  const { feedId, categoryId, unreadOnly, starredOnly, hasSummary, graphAdded, first, after, preserveIds } =
    params;

  // Get the keep vector (average of keep=true embeddings)
  const keepVector = await getKeepVector();

  if (!keepVector) {
    log.error({ feedId, categoryId }, "No keep vector available, falling back to newest sort");
    return NextResponse.json({
      edges: [],
      pageInfo: {
        hasNextPage: false,
        hasPreviousPage: false,
        startCursor: null,
        endCursor: null,
      },
      totalCount: 0,
    });
  }

  // Format keep vector for pgvector
  const vectorStr = `[${keepVector.join(",")}]`;

  // Helper to build common conditions (without unread filter)
  const buildCommonConditions = (): string[] => {
    const conds: string[] = ["embedding IS NOT NULL"];
    if (feedId) {
      conds.push(`feed_id = '${feedId}'`);
    }
    if (categoryId) {
      conds.push(
        `feed_id IN (SELECT id FROM feeds WHERE category_id = '${categoryId}')`
      );
    }
    if (starredOnly) {
      conds.push("is_starred = true");
    }
    if (hasSummary === true) {
      conds.push("summary IS NOT NULL AND summary != ''");
    } else if (hasSummary === false) {
      conds.push("(summary IS NULL OR summary = '')");
    }
    if (graphAdded === true) {
      conds.push("graph_added_at IS NOT NULL");
    } else if (graphAdded === false) {
      conds.push("graph_added_at IS NULL");
      conds.push("filtered_content IS NOT NULL AND filtered_content != ''");
    }
    return conds;
  };

  // Helper to add cursor condition
  const addCursorCondition = (conds: string[]) => {
    if (after) {
      const cursor = decodeRecommendedCursor(after);
      if (cursor) {
        const cursorScoreSubquery = `(SELECT e2.embedding <=> '${vectorStr}'::vector FROM entries e2 WHERE e2.id = '${cursor.id}')`;
        conds.push(
          `(e.embedding <=> '${vectorStr}'::vector > ${cursorScoreSubquery} ` +
          `OR (e.embedding <=> '${vectorStr}'::vector = ${cursorScoreSubquery} AND e.id > '${cursor.id}'))`
        );
      }
    }
  };

  // SQL select clause for entries
  const selectClause = `
    SELECT
      e.id,
      e.feed_id,
      f.name as feed_name,
      e.title,
      e.url,
      e.summary,
      e.author,
      e.published_at,
      e.is_read,
      e.is_starred,
      e.keep,
      e.thumbnail_url,
      e.metadata,
      e.created_at,
      (e.embedding <=> '${vectorStr}'::vector) as similarity_score
    FROM entries e
    LEFT JOIN feeds f ON e.feed_id = f.id
  `;

  // Special handling for unreadOnly with preserveIds
  if (unreadOnly && preserveIds.length > 0) {
    const escapedPreserveIds = preserveIds.map((id) => `'${id.replace(/'/g, "''")}'`).join(",");

    // 1. Count: unread entries + preserved entries
    const countConditions = buildCommonConditions();
    countConditions.push(`(is_read = false OR id IN (${escapedPreserveIds}))`);
    const countResult = await db.execute<{ count: string }>(sql.raw(`
      SELECT COUNT(*) as count
      FROM entries
      WHERE ${countConditions.join(" AND ")}
    `));
    const totalCount = Number(countResult.rows[0]?.count || 0);

    // 2. Fetch unread entries (excluding preserveIds)
    const unreadConditions = buildCommonConditions();
    unreadConditions.push("is_read = false");
    unreadConditions.push(`id NOT IN (${escapedPreserveIds})`);
    addCursorCondition(unreadConditions);

    const unreadResult = await db.execute<RecommendedResultRow>(sql.raw(`
      ${selectClause}
      WHERE ${unreadConditions.join(" AND ")}
      ORDER BY similarity_score ASC, e.id ASC
      LIMIT ${first + 1}
    `));

    const hasNextPageUnread = unreadResult.rows.length > first;
    const unreadRows = unreadResult.rows.slice(0, first);

    // 3. Fetch preserved entries (read entries in preserveIds) - only on first page
    let preservedRows: RecommendedResultRow[] = [];
    if (!after) {
      const preservedConditions = buildCommonConditions();
      preservedConditions.push("is_read = true");
      preservedConditions.push(`id IN (${escapedPreserveIds})`);

      const preservedResult = await db.execute<RecommendedResultRow>(sql.raw(`
        ${selectClause}
        WHERE ${preservedConditions.join(" AND ")}
        ORDER BY similarity_score ASC, e.id ASC
      `));
      preservedRows = preservedResult.rows;
    }

    // 4. Merge by similarity score order
    const allRows = [...unreadRows, ...preservedRows];

    // Sort by similarity_score (ascending - lower is more similar) and id as tiebreaker
    allRows.sort((a, b) => {
      if (a.similarity_score !== b.similarity_score) {
        return a.similarity_score - b.similarity_score;
      }
      return a.id.localeCompare(b.id);
    });

    const edges = allRows.map((row) => ({
      node: rowToNode(row),
      cursor: encodeRecommendedCursor(row.similarity_score, row.id),
    }));

    return NextResponse.json({
      edges,
      pageInfo: {
        hasNextPage: hasNextPageUnread,
        hasPreviousPage: !!after,
        startCursor: edges.length > 0 ? edges[0].cursor : null,
        endCursor: edges.length > 0 ? edges[edges.length - 1].cursor : null,
      },
      totalCount,
    });
  }

  // Standard flow (no preserveIds or not unreadOnly)
  const baseConditions = buildCommonConditions();
  if (unreadOnly) {
    baseConditions.push("is_read = false");
  }

  const whereConditions = [...baseConditions];
  addCursorCondition(whereConditions);

  // Get total count
  const countResult = await db.execute<{ count: string }>(sql.raw(`
    SELECT COUNT(*) as count
    FROM entries
    WHERE ${baseConditions.join(" AND ")}
  `));
  const totalCount = Number(countResult.rows[0]?.count || 0);

  // Query entries
  const result = await db.execute<RecommendedResultRow>(sql.raw(`
    ${selectClause}
    WHERE ${whereConditions.join(" AND ")}
    ORDER BY similarity_score ASC, e.id ASC
    LIMIT ${first + 1}
  `));

  const hasNextPage = result.rows.length > first;
  const edges = result.rows.slice(0, first).map((row) => ({
    node: rowToNode(row),
    cursor: encodeRecommendedCursor(row.similarity_score, row.id),
  }));

  return NextResponse.json({
    edges,
    pageInfo: {
      hasNextPage,
      hasPreviousPage: !!after,
      startCursor: edges.length > 0 ? edges[0].cursor : null,
      endCursor: edges.length > 0 ? edges[edges.length - 1].cursor : null,
    },
    totalCount,
  });
}

// Cursor format: { publishedAt: string, id: string }
interface Cursor {
  publishedAt: string;
  id: string;
}

function encodeCursor(publishedAt: Date | string | null, id: string): string {
  const cursor: Cursor = {
    publishedAt: publishedAt
      ? new Date(publishedAt).toISOString()
      : new Date(0).toISOString(),
    id,
  };
  return Buffer.from(JSON.stringify(cursor)).toString("base64url");
}

function decodeCursor(cursor: string): Cursor | null {
  try {
    const decoded = Buffer.from(cursor, "base64url").toString("utf-8");
    return JSON.parse(decoded) as Cursor;
  } catch {
    return null;
  }
}

// GET /api/entries - List entries with connection-based pagination
export async function GET(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const feedId = searchParams.get("feedId");
    const categoryId = searchParams.get("categoryId");
    const unreadOnly = searchParams.get("unreadOnly") === "true";
    const starredOnly = searchParams.get("starredOnly") === "true";
    const hasSummaryParam = searchParams.get("hasSummary");
    const hasSummary =
      hasSummaryParam === "true"
        ? true
        : hasSummaryParam === "false"
          ? false
          : undefined;
    const graphAddedParam = searchParams.get("graphAdded");
    const graphAdded =
      graphAddedParam === "true"
        ? true
        : graphAddedParam === "false"
          ? false
          : undefined;
    const keepOnly = searchParams.get("keepOnly") === "true";
    const first = Math.min(parseInt(searchParams.get("first") || "50"), 100);
    const after = searchParams.get("after");
    const sort = (searchParams.get("sort") as SortMode) || "newest";
    // Parse preserveIds - comma-separated list of entry IDs to include even if read
    const preserveIdsParam = searchParams.get("preserveIds");
    const preserveIds = preserveIdsParam ? preserveIdsParam.split(",").filter(Boolean) : [];

    // Handle recommended sort separately (uses embedding similarity)
    if (sort === "recommended") {
      return handleRecommendedSort(request, {
        feedId,
        categoryId,
        unreadOnly,
        starredOnly,
        hasSummary,
        graphAdded,
        first,
        after,
        preserveIds,
      });
    }

    // Determine sort direction for newest/oldest
    const isAscending = sort === "oldest";

    // Helper to build common conditions (without unread/cursor filters)
    const buildCommonConditions = () => {
      const conds = [];
      if (feedId) {
        conds.push(eq(entries.feedId, feedId));
      }
      if (categoryId) {
        const feedsInCategory = db
          .select({ id: feeds.id })
          .from(feeds)
          .where(eq(feeds.categoryId, categoryId));
        conds.push(sql`${entries.feedId} IN (${feedsInCategory})`);
      }
      if (starredOnly) {
        conds.push(eq(entries.isStarred, true));
      }
      if (hasSummary === true) {
        conds.push(sql`${entries.summary} IS NOT NULL AND ${entries.summary} != ''`);
      } else if (hasSummary === false) {
        conds.push(sql`${entries.summary} IS NULL OR ${entries.summary} = ''`);
      }
      if (graphAdded === true) {
        conds.push(isNotNull(entries.graphAddedAt));
      } else if (graphAdded === false) {
        conds.push(isNull(entries.graphAddedAt));
        conds.push(sql`${entries.filteredContent} IS NOT NULL AND ${entries.filteredContent} != ''`);
      }
      if (keepOnly) {
        conds.push(eq(entries.keep, true));
      }
      return conds;
    };

    // Helper to add cursor condition
    const addCursorCondition = (conds: ReturnType<typeof buildCommonConditions>) => {
      if (after) {
        const cursor = decodeCursor(after);
        if (cursor) {
          const cursorDate = new Date(cursor.publishedAt);
          if (isAscending) {
            conds.push(
              sql`(${entries.publishedAt} > ${cursorDate} OR (${entries.publishedAt} = ${cursorDate} AND ${entries.id} > ${cursor.id}))`
            );
          } else {
            conds.push(
              sql`(${entries.publishedAt} < ${cursorDate} OR (${entries.publishedAt} = ${cursorDate} AND ${entries.id} < ${cursor.id}))`
            );
          }
        }
      }
    };

    const orderByPublishedAt = isAscending
      ? asc(entries.publishedAt)
      : desc(entries.publishedAt);
    const orderById = isAscending ? asc(entries.id) : desc(entries.id);

    // Entry select fields
    const entrySelectFields = {
      id: entries.id,
      feedId: entries.feedId,
      feedName: feeds.name,
      title: entries.title,
      url: entries.url,
      summary: entries.summary,
      author: entries.author,
      publishedAt: entries.publishedAt,
      isRead: entries.isRead,
      isStarred: entries.isStarred,
      keep: entries.keep,
      thumbnailUrl: entries.thumbnailUrl,
      metadata: entries.metadata,
      createdAt: entries.createdAt,
    };

    // Special handling for unreadOnly with preserveIds:
    // Fetch unread entries and preserved entries separately, then merge
    if (unreadOnly && preserveIds.length > 0) {
      const escapedPreserveIds = preserveIds.map((id) => `'${id.replace(/'/g, "''")}'`).join(",");

      // 1. Count: unread entries + preserved entries (for total)
      const baseConditions = buildCommonConditions();
      baseConditions.push(
        sql`(${entries.isRead} = false OR ${entries.id} IN (${sql.raw(escapedPreserveIds)}))`
      );
      const countResult = await db
        .select({ count: sql<number>`count(*)` })
        .from(entries)
        .leftJoin(feeds, eq(entries.feedId, feeds.id))
        .where(and(...baseConditions));
      const totalCount = Number(countResult[0]?.count || 0);

      // 2. Fetch unread entries (excluding preserveIds to avoid duplicates)
      const unreadConditions = buildCommonConditions();
      unreadConditions.push(eq(entries.isRead, false));
      // Exclude preserveIds from unread query to avoid duplicates
      unreadConditions.push(
        sql`${entries.id} NOT IN (${sql.raw(escapedPreserveIds)})`
      );
      addCursorCondition(unreadConditions);

      const unreadResult = await db
        .select(entrySelectFields)
        .from(entries)
        .leftJoin(feeds, eq(entries.feedId, feeds.id))
        .where(and(...unreadConditions))
        .orderBy(orderByPublishedAt, orderById)
        .limit(first + 1);

      const hasNextPageUnread = unreadResult.length > first;
      const unreadEntries = unreadResult.slice(0, first);

      // 3. Fetch preserved entries (read entries in preserveIds)
      // Only fetch on first page (no cursor) to append at the end
      let preservedEntries: typeof unreadEntries = [];
      if (!after) {
        const preservedConditions = buildCommonConditions();
        preservedConditions.push(eq(entries.isRead, true));
        preservedConditions.push(
          sql`${entries.id} IN (${sql.raw(escapedPreserveIds)})`
        );

        preservedEntries = await db
          .select(entrySelectFields)
          .from(entries)
          .leftJoin(feeds, eq(entries.feedId, feeds.id))
          .where(and(...preservedConditions))
          .orderBy(orderByPublishedAt, orderById);
      }

      // 4. Merge by date order (preserveIds entries are already sorted, just need to merge)
      const allEntries = [...unreadEntries, ...preservedEntries];

      // Sort by publishedAt (respecting sort direction) and id as tiebreaker
      allEntries.sort((a, b) => {
        const dateA = a.publishedAt ? new Date(a.publishedAt).getTime() : 0;
        const dateB = b.publishedAt ? new Date(b.publishedAt).getTime() : 0;
        if (dateA !== dateB) {
          return isAscending ? dateA - dateB : dateB - dateA;
        }
        // Tiebreaker by id
        return isAscending ? a.id.localeCompare(b.id) : b.id.localeCompare(a.id);
      });

      const edges = allEntries.map((entry) => ({
        node: entry,
        cursor: encodeCursor(entry.publishedAt, entry.id),
      }));

      const pageInfo = {
        hasNextPage: hasNextPageUnread,
        hasPreviousPage: !!after,
        startCursor: edges.length > 0 ? edges[0].cursor : null,
        endCursor: edges.length > 0 ? edges[edges.length - 1].cursor : null,
      };

      return NextResponse.json({
        edges,
        pageInfo,
        totalCount,
      });
    }

    // Standard flow (no preserveIds or not unreadOnly)
    const conditions = buildCommonConditions();

    if (unreadOnly) {
      conditions.push(eq(entries.isRead, false));
    }

    addCursorCondition(conditions);

    const whereClause = conditions.length > 0 ? and(...conditions) : undefined;

    // Build base conditions for total count (without cursor)
    const baseConditions = buildCommonConditions();
    if (unreadOnly) {
      baseConditions.push(eq(entries.isRead, false));
    }
    const baseWhereClause =
      baseConditions.length > 0 ? and(...baseConditions) : undefined;

    // Get total count
    const countResult = await db
      .select({ count: sql<number>`count(*)` })
      .from(entries)
      .leftJoin(feeds, eq(entries.feedId, feeds.id))
      .where(baseWhereClause);
    const totalCount = Number(countResult[0]?.count || 0);

    const result = await db
      .select(entrySelectFields)
      .from(entries)
      .leftJoin(feeds, eq(entries.feedId, feeds.id))
      .where(whereClause)
      .orderBy(orderByPublishedAt, orderById)
      .limit(first + 1);

    const hasNextPage = result.length > first;
    const edges = result.slice(0, first).map((entry) => ({
      node: entry,
      cursor: encodeCursor(entry.publishedAt, entry.id),
    }));

    const pageInfo = {
      hasNextPage,
      hasPreviousPage: !!after,
      startCursor: edges.length > 0 ? edges[0].cursor : null,
      endCursor: edges.length > 0 ? edges[edges.length - 1].cursor : null,
    };

    return NextResponse.json({
      edges,
      pageInfo,
      totalCount,
    });
  } catch (error) {
    log.error({ error, message: error instanceof Error ? error.message : String(error), stack: error instanceof Error ? error.stack : undefined }, "failed to fetch entries");
    return NextResponse.json(
      { error: "Failed to fetch entries" },
      { status: 500 }
    );
  }
}

// POST /api/entries - Create a new entry
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const {
      feedId,
      title,
      url,
      feedContent,
      fullContent,
      filteredContent,
      rawHtml,
      summary,
      author,
      publishedAt,
      metadata,
    } = body;

    if (!feedId || typeof feedId !== "string") {
      return NextResponse.json(
        { error: "feedId is required" },
        { status: 400 }
      );
    }
    if (!title || typeof title !== "string") {
      return NextResponse.json(
        { error: "title is required" },
        { status: 400 }
      );
    }
    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "url is required" }, { status: 400 });
    }

    const result = await createEntry({
      feedId,
      title,
      url,
      feedContent,
      fullContent,
      filteredContent,
      rawHtml,
      summary,
      author: author || null,
      publishedAt: publishedAt ? new Date(publishedAt) : null,
      metadata: metadata || null,
    });

    if (isError(result)) {
      const status = result.error === "Feed not found" ? 404 : 409;
      return NextResponse.json(result, { status });
    }

    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    log.error({ error }, "failed to create entry");
    return NextResponse.json(
      { error: "Failed to create entry" },
      { status: 500 }
    );
  }
}
