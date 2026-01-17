import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries } from "@/db/schema";
import { inArray, sql } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:mark-graph-added");

// POST /api/entries/mark-graph-added - Mark entries as added to graph
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { entryIds } = body;

    if (!Array.isArray(entryIds) || entryIds.length === 0) {
      return NextResponse.json(
        { error: "entryIds must be a non-empty array" },
        { status: 400 }
      );
    }

    // Validate all IDs are strings
    if (!entryIds.every((id) => typeof id === "string")) {
      return NextResponse.json(
        { error: "All entryIds must be strings" },
        { status: 400 }
      );
    }

    // Update graphAddedAt for all specified entries
    const result = await db
      .update(entries)
      .set({ graphAddedAt: sql`NOW()` })
      .where(inArray(entries.id, entryIds));

    const updatedCount = result.rowCount ?? 0;

    log.info({ entryIds, updatedCount }, "marked entries as graph-added");

    return NextResponse.json({ updatedCount });
  } catch (error) {
    log.error({ error }, "failed to mark entries as graph-added");
    return NextResponse.json(
      { error: "Failed to mark entries as graph-added" },
      { status: 500 }
    );
  }
}
