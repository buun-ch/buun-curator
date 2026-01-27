import { asc } from "drizzle-orm";
import { NextResponse } from "next/server";

import { db } from "@/db";
import { feeds } from "@/db/schema";
import { getSettings } from "@/lib/api/settings";
import { createLogger } from "@/lib/logger";
import { startSingleFeedIngestionWorkflow } from "@/lib/temporal";

const log = createLogger("api:feeds");

// GET /api/feeds - List all feeds
export async function GET() {
  try {
    const result = await db.select().from(feeds).orderBy(asc(feeds.name));

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "failed to fetch feeds");
    return NextResponse.json(
      { error: "Failed to fetch feeds" },
      { status: 500 },
    );
  }
}

// POST /api/feeds - Create a new feed
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name, url, siteUrl, categoryId, type, fetchContent, fetchLimit } =
      body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "Name is required" }, { status: 400 });
    }

    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "URL is required" }, { status: 400 });
    }

    const result = await db
      .insert(feeds)
      .values({
        name,
        url,
        siteUrl: siteUrl || null,
        categoryId: categoryId || null,
        type: type || null,
        fetchContent: fetchContent ?? true,
        fetchLimit: fetchLimit ?? 20,
      })
      .returning();

    const feed = result[0];

    // Trigger single feed ingestion workflow
    try {
      const settings = await getSettings();
      const handle = await startSingleFeedIngestionWorkflow({
        feedId: feed.id,
        feedName: feed.name,
        feedUrl: feed.url,
        fetchLimit: feed.fetchLimit,
        autoDistill: true,
        enableContentFetch: feed.fetchContent,
        targetLanguage: settings.targetLanguage ?? "",
        enableThumbnail: true,
        domainFetchDelay: 2.0,
        maxEntryAgeDays: 0, // No limit for new feeds
      });
      log.info(
        { feedName: feed.name, workflowId: handle.workflowId },
        "started ingestion workflow for new feed",
      );
    } catch (workflowError) {
      // Log error but don't fail the feed creation
      log.error(
        { feedName: feed.name, error: workflowError },
        "failed to start ingestion workflow",
      );
    }

    return NextResponse.json(feed, { status: 201 });
  } catch (error) {
    log.error({ error }, "failed to create feed");
    return NextResponse.json(
      { error: "Failed to create feed" },
      { status: 500 },
    );
  }
}
