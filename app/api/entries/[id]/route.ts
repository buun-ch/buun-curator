import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, feeds, entryLabels, labels } from "@/db/schema";
import { eq } from "drizzle-orm";
import { updateEntry as updateEntryApi, isError } from "@/lib/api";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// GET /api/entries/[id] - Get a single entry with full content
export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const [entry] = await db
      .select({
        id: entries.id,
        feedId: entries.feedId,
        feedName: feeds.name,
        feedSiteUrl: feeds.siteUrl,
        title: entries.title,
        url: entries.url,
        feedContent: entries.feedContent,
        fullContent: entries.fullContent,
        filteredContent: entries.filteredContent,
        translatedContent: entries.translatedContent,
        summary: entries.summary,
        author: entries.author,
        publishedAt: entries.publishedAt,
        isRead: entries.isRead,
        isStarred: entries.isStarred,
        keep: entries.keep,
        thumbnailUrl: entries.thumbnailUrl,
        metadata: entries.metadata,
        createdAt: entries.createdAt,
        updatedAt: entries.updatedAt,
      })
      .from(entries)
      .leftJoin(feeds, eq(entries.feedId, feeds.id))
      .where(eq(entries.id, entryId));

    if (!entry) {
      return NextResponse.json({ error: "Entry not found" }, { status: 404 });
    }

    // Fetch labels for this entry
    const entryLabelsList = await db
      .select({
        id: labels.id,
        name: labels.name,
        color: labels.color,
      })
      .from(entryLabels)
      .innerJoin(labels, eq(entryLabels.labelId, labels.id))
      .where(eq(entryLabels.entryId, entryId));

    return NextResponse.json({
      ...entry,
      labels: entryLabelsList,
    });
  } catch (error) {
    log.error({ error }, "failed to fetch entry");
    return NextResponse.json(
      { error: "Failed to fetch entry" },
      { status: 500 }
    );
  }
}

// PATCH /api/entries/[id] - Update entry (read status, starred, content, etc.)
export async function PATCH(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const body = await request.json();
    const {
      isRead,
      isStarred,
      keep,
      fullContent,
      translatedContent,
      filteredContent,
      rawHtml,
      summary,
      thumbnailUrl,
      metadata,
    } = body;

    // Build update data for lib/api
    const updateData: {
      isRead?: boolean;
      isStarred?: boolean;
      keep?: boolean;
      fullContent?: string;
      translatedContent?: string;
      filteredContent?: string;
      rawHtml?: string;
      summary?: string;
      thumbnailUrl?: string;
      metadata?: Record<string, unknown>;
    } = {};

    if (typeof isRead === "boolean") {
      updateData.isRead = isRead;
    }
    if (typeof isStarred === "boolean") {
      updateData.isStarred = isStarred;
    }
    if (typeof keep === "boolean") {
      updateData.keep = keep;
    }
    if (typeof fullContent === "string") {
      updateData.fullContent = fullContent;
    }
    if (typeof translatedContent === "string") {
      updateData.translatedContent = translatedContent;
    }
    if (typeof filteredContent === "string") {
      updateData.filteredContent = filteredContent;
    }
    if (typeof rawHtml === "string") {
      updateData.rawHtml = rawHtml;
    }
    if (typeof summary === "string") {
      updateData.summary = summary;
    }
    if (typeof thumbnailUrl === "string") {
      updateData.thumbnailUrl = thumbnailUrl;
    }
    if (metadata !== undefined) {
      updateData.metadata = metadata;
    }

    // Only call updateEntryApi if there are fields to update
    if (Object.keys(updateData).length === 0) {
      return NextResponse.json({ error: "No fields to update" }, { status: 400 });
    }

    const result = await updateEntryApi(entryId, updateData);

    if (isError(result)) {
      return NextResponse.json({ error: result.error }, { status: 404 });
    }

    return NextResponse.json({
      id: result.id,
      isRead: result.isRead,
      isStarred: result.isStarred,
      keep: result.keep,
      fullContent: result.fullContent,
      translatedContent: result.translatedContent,
      filteredContent: result.filteredContent,
      rawHtml: result.rawHtml,
      summary: result.summary,
      thumbnailUrl: result.thumbnailUrl,
      metadata: result.metadata,
    });
  } catch (error) {
    log.error({ error }, "failed to update entry");
    return NextResponse.json(
      { error: "Failed to update entry" },
      { status: 500 }
    );
  }
}
