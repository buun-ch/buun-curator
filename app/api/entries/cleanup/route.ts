import { and, eq, lt, sql } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";

import { db } from "@/db";
import { entries } from "@/db/schema";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:cleanup");

/**
 * POST /api/entries/cleanup - Delete old entries that meet cleanup criteria.
 *
 * Criteria:
 * - isRead = true
 * - isStarred = false
 * - keep = false
 * - publishedAt is older than the specified days (default: 7)
 *
 * Request body:
 * - olderThanDays: number (optional, default: 7)
 * - dryRun: boolean (optional, default: false) - if true, only count without deleting
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const olderThanDays = body.olderThanDays ?? 7;
    const dryRun = body.dryRun ?? false;

    if (typeof olderThanDays !== "number" || olderThanDays < 1) {
      return NextResponse.json(
        { error: "olderThanDays must be a positive number" },
        { status: 400 },
      );
    }

    // Calculate the cutoff date
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

    // Build the where clause:
    // isRead = true AND isStarred = false AND keep = false AND publishedAt < cutoffDate
    const whereClause = and(
      eq(entries.isRead, true),
      eq(entries.isStarred, false),
      eq(entries.keep, false),
      lt(entries.publishedAt, cutoffDate),
    );

    if (dryRun) {
      // Count only
      const countResult = await db
        .select({ count: sql<number>`count(*)::int` })
        .from(entries)
        .where(whereClause);

      const count = countResult[0]?.count ?? 0;

      log.info(
        { olderThanDays, cutoffDate: cutoffDate.toISOString(), count },
        "dry run: counted entries for cleanup",
      );

      return NextResponse.json({
        dryRun: true,
        count,
        olderThanDays,
        cutoffDate: cutoffDate.toISOString(),
      });
    }

    // Delete entries matching the criteria and return their IDs
    const deletedRows = await db
      .delete(entries)
      .where(whereClause)
      .returning({ id: entries.id });

    const deletedCount = deletedRows.length;
    const deletedIds = deletedRows.map((row) => row.id);

    log.info(
      { olderThanDays, cutoffDate: cutoffDate.toISOString(), deletedCount },
      "deleted old entries",
    );

    return NextResponse.json({
      deletedCount,
      deletedIds,
      olderThanDays,
      cutoffDate: cutoffDate.toISOString(),
    });
  } catch (error) {
    log.error({ error }, "failed to cleanup old entries");
    return NextResponse.json(
      { error: "Failed to cleanup old entries" },
      { status: 500 },
    );
  }
}
