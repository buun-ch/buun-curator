import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";

import { db } from "@/db";
import { feeds } from "@/db/schema";
import { getSettings } from "@/lib/api/settings";
import { createLogger } from "@/lib/logger";
import { startSingleFeedIngestionWorkflow } from "@/lib/temporal";

const log = createLogger("api:feeds");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// GET /api/feeds/[id] - Get a single feed
export async function GET(request: Request, { params }: RouteParams) {
  try {
    const { id: feedId } = await params;

    const result = await db
      .select()
      .from(feeds)
      .where(eq(feeds.id, feedId))
      .limit(1);

    if (result.length === 0) {
      return NextResponse.json({ error: "Feed not found" }, { status: 404 });
    }

    return NextResponse.json(result[0]);
  } catch (error) {
    log.error({ error }, "failed to fetch feed");
    return NextResponse.json(
      { error: "Failed to fetch feed" },
      { status: 500 },
    );
  }
}

// PATCH /api/feeds/[id] - Update a feed
export async function PATCH(request: Request, { params }: RouteParams) {
  try {
    const { id: feedId } = await params;

    const body = await request.json();
    const { name, url, siteUrl, categoryId, fetchContent, fetchLimit } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "Name is required" }, { status: 400 });
    }

    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "URL is required" }, { status: 400 });
    }

    const result = await db
      .update(feeds)
      .set({
        name,
        url,
        siteUrl: siteUrl || null,
        categoryId: categoryId || null,
        fetchContent: fetchContent ?? true,
        fetchLimit: fetchLimit ?? 20,
        updatedAt: new Date(),
      })
      .where(eq(feeds.id, feedId))
      .returning();

    if (result.length === 0) {
      return NextResponse.json({ error: "Feed not found" }, { status: 404 });
    }

    const feed = result[0];

    // Trigger single feed ingestion workflow
    try {
      const settings = await getSettings();
      const handle = await startSingleFeedIngestionWorkflow({
        feedId: feed.id,
        feedName: feed.name,
        feedUrl: feed.url,
        etag: feed.etag ?? "",
        lastModified: feed.lastModified ?? "",
        fetchLimit: feed.fetchLimit,
        autoDistill: true,
        enableContentFetch: feed.fetchContent,
        targetLanguage: settings.targetLanguage ?? "",
        enableThumbnail: true,
        domainFetchDelay: 2.0,
      });
      log.info(
        { feedName: feed.name, workflowId: handle.workflowId },
        "started ingestion workflow for updated feed",
      );
    } catch (workflowError) {
      // Log error but don't fail the feed update
      log.error(
        { feedName: feed.name, error: workflowError },
        "failed to start ingestion workflow",
      );
    }

    return NextResponse.json(feed);
  } catch (error) {
    log.error({ error }, "failed to update feed");
    return NextResponse.json(
      { error: "Failed to update feed" },
      { status: 500 },
    );
  }
}

// DELETE /api/feeds/[id] - Delete a feed
export async function DELETE(request: Request, { params }: RouteParams) {
  try {
    const { id: feedId } = await params;

    const result = await db
      .delete(feeds)
      .where(eq(feeds.id, feedId))
      .returning();

    if (result.length === 0) {
      return NextResponse.json({ error: "Feed not found" }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "failed to delete feed");
    return NextResponse.json(
      { error: "Failed to delete feed" },
      { status: 500 },
    );
  }
}
