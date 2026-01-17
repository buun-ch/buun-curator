import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, feeds } from "@/db/schema";
import { eq } from "drizzle-orm";
import { createLogger } from "@/lib/logger";
import { startReprocessEntriesWorkflow } from "@/lib/temporal";

const log = createLogger("api:entries:refetch");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// POST /api/entries/[id]/refetch - Trigger workflow to refetch content for an entry
export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    // Get entry with its feed's fetchContent setting
    const [entryWithFeed] = await db
      .select({
        id: entries.id,
        feedId: entries.feedId,
        feedFetchContent: feeds.fetchContent,
      })
      .from(entries)
      .leftJoin(feeds, eq(entries.feedId, feeds.id))
      .where(eq(entries.id, entryId));

    if (!entryWithFeed) {
      return NextResponse.json({ error: "Entry not found" }, { status: 404 });
    }

    // Check if feed has fetchContent disabled
    const shouldFetchContent = entryWithFeed.feedFetchContent !== false;

    log.debug(
      { entryId, feedId: entryWithFeed.feedId, shouldFetchContent },
      "Refetch entry"
    );

    // If fetchContent is disabled, clear fetched content fields first
    // (in case the feed option was changed from true to false)
    if (!shouldFetchContent) {
      await db
        .update(entries)
        .set({
          fullContent: "",
          filteredContent: "",
          rawHtml: "",
          summary: "",
          updatedAt: new Date(),
        })
        .where(eq(entries.id, entryId));
    }

    // Start the Temporal workflow
    // Even if fetchContent is disabled, we still run the workflow with summarize=true
    // so that feedContent can be used as a fallback for summarization
    const handle = await startReprocessEntriesWorkflow({
      entryIds: [entryId],
      fetchContent: shouldFetchContent,
      summarize: true,
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      entryId: entryWithFeed.id,
    });
  } catch (error) {
    log.error({ error }, "Failed to start refetch workflow");
    return NextResponse.json(
      { error: "Failed to start refetch workflow" },
      { status: 500 }
    );
  }
}
