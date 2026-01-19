import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, feeds } from "@/db/schema";
import { eq, and, sql } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries");

// POST /api/entries/mark-all-read - Mark all entries as read
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { feedId, categoryId } = body;

    const conditions = [eq(entries.isRead, false)];

    if (feedId) {
      conditions.push(eq(entries.feedId, feedId));
    }

    if (categoryId) {
      // Filter by category through feeds table
      const feedsInCategory = db
        .select({ id: feeds.id })
        .from(feeds)
        .where(eq(feeds.categoryId, categoryId));
      conditions.push(sql`${entries.feedId} IN (${feedsInCategory})`);
    }

    const whereClause = and(...conditions);

    const result = await db
      .update(entries)
      .set({
        isRead: true,
        updatedAt: new Date(),
      })
      .where(whereClause)
      .returning({ id: entries.id });

    return NextResponse.json({
      success: true,
      updatedCount: result.length,
    });
  } catch (error) {
    log.error({ error }, "failed to mark entries as read");
    return NextResponse.json(
      { error: "Failed to mark entries as read" },
      { status: 500 },
    );
  }
}
