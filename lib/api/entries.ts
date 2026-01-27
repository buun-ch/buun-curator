/**
 * Entry-related database operations.
 *
 * @module lib/api/entries
 */

import { desc, eq } from "drizzle-orm";

import { db as defaultDb } from "@/db";
import { entries, feeds } from "@/db/schema";

import type { Db } from "./types";
import { DEFAULT_FETCH_LIMIT, MAX_FETCH_LIMIT } from "./types";

/**
 * Gets a specific entry by ID with full details including content fields.
 *
 * @param entryId - The entry's unique identifier
 * @param db - Database instance (defaults to the main db)
 * @returns The entry object with feed name, or null if not found
 */
export async function getEntry(entryId: string, db: Db = defaultDb) {
  const [entry] = await db
    .select({
      id: entries.id,
      feedId: entries.feedId,
      feedName: feeds.name,
      title: entries.title,
      url: entries.url,
      feedContent: entries.feedContent,
      fullContent: entries.fullContent,
      filteredContent: entries.filteredContent,
      translatedContent: entries.translatedContent,
      rawHtml: entries.rawHtml,
      summary: entries.summary,
      author: entries.author,
      publishedAt: entries.publishedAt,
      isRead: entries.isRead,
      isStarred: entries.isStarred,
      metadata: entries.metadata,
      createdAt: entries.createdAt,
      updatedAt: entries.updatedAt,
    })
    .from(entries)
    .leftJoin(feeds, eq(entries.feedId, feeds.id))
    .where(eq(entries.id, entryId));

  return entry || null;
}

/**
 * Creates a new entry for a feed.
 *
 * Uses a database transaction to atomically check for duplicate URLs
 * and insert the new entry. This prevents race conditions when multiple
 * workers are ingesting the same feed concurrently.
 *
 * @param data - Entry data including feedId, title, url, and optional content
 * @param db - Database instance (defaults to the main db)
 * @returns The created entry, or error if feed not found or URL exists
 */
export async function createEntry(
  data: {
    feedId: string;
    title: string;
    url: string;
    feedContent?: string;
    fullContent?: string;
    filteredContent?: string;
    rawHtml?: string;
    summary?: string;
    author?: string | null;
    publishedAt?: Date | null;
    metadata?: Record<string, unknown> | null;
  },
  db: Db = defaultDb,
) {
  return await db.transaction(async (tx) => {
    // Verify feed exists
    const [feed] = await tx
      .select({ id: feeds.id })
      .from(feeds)
      .where(eq(feeds.id, data.feedId));

    if (!feed) {
      return { error: "Feed not found" };
    }

    // Check for duplicate URL (within transaction for consistency)
    const [existingEntry] = await tx
      .select({ id: entries.id })
      .from(entries)
      .where(eq(entries.url, data.url));

    if (existingEntry) {
      return {
        error: "Entry with this URL already exists",
        existingEntryId: existingEntry.id,
      };
    }

    const [entry] = await tx
      .insert(entries)
      .values({
        feedId: data.feedId,
        title: data.title,
        url: data.url,
        feedContent: data.feedContent || "",
        fullContent: data.fullContent || "",
        filteredContent: data.filteredContent || "",
        rawHtml: data.rawHtml || "",
        summary: data.summary || "",
        author: data.author || null,
        publishedAt: data.publishedAt || null,
        metadata: data.metadata || null,
      })
      .returning();

    return entry;
  });
}

/**
 * Updates an existing entry's content and/or metadata.
 *
 * When metadata is provided, uses a transaction to read-modify-write
 * and merge with existing metadata, preventing lost updates from
 * concurrent modifications.
 *
 * @param entryId - The entry's unique identifier
 * @param data - Fields to update (content, summary, read/star status, metadata)
 * @param db - Database instance (defaults to the main db)
 * @returns Success result with updated fields, or error if entry not found
 */
export async function updateEntry(
  entryId: string,
  data: {
    fullContent?: string;
    translatedContent?: string;
    filteredContent?: string;
    rawHtml?: string;
    summary?: string;
    annotation?: string;
    isRead?: boolean;
    isStarred?: boolean;
    keep?: boolean;
    thumbnailUrl?: string;
    metadata?: Record<string, unknown>;
  },
  db: Db = defaultDb,
) {
  // Use transaction only when metadata merge is needed
  if (data.metadata !== undefined) {
    return await db.transaction(async (tx) => {
      const updateData: {
        fullContent?: string;
        translatedContent?: string;
        filteredContent?: string;
        rawHtml?: string;
        summary?: string;
        annotation?: string;
        isRead?: boolean;
        isStarred?: boolean;
        keep?: boolean;
        thumbnailUrl?: string;
        metadata?: Record<string, unknown>;
        updatedAt: Date;
      } = {
        updatedAt: new Date(),
      };

      if (data.fullContent !== undefined) {
        updateData.fullContent = data.fullContent;
      }
      if (data.translatedContent !== undefined) {
        updateData.translatedContent = data.translatedContent;
      }
      if (data.filteredContent !== undefined) {
        updateData.filteredContent = data.filteredContent;
      }
      // if (data.rawHtml !== undefined) {
      //   updateData.rawHtml = data.rawHtml;
      // }
      if (data.summary !== undefined) {
        updateData.summary = data.summary;
      }
      if (data.annotation !== undefined) {
        updateData.annotation = data.annotation;
      }
      if (data.isRead !== undefined) {
        updateData.isRead = data.isRead;
      }
      if (data.isStarred !== undefined) {
        updateData.isStarred = data.isStarred;
      }
      if (data.keep !== undefined) {
        updateData.keep = data.keep;
      }
      if (data.thumbnailUrl !== undefined) {
        updateData.thumbnailUrl = data.thumbnailUrl;
      }

      // Fetch existing entry to get current metadata (within transaction)
      const [existing] = await tx
        .select({ metadata: entries.metadata })
        .from(entries)
        .where(eq(entries.id, entryId));

      if (existing) {
        const existingMetadata =
          (existing.metadata as Record<string, unknown>) || {};
        updateData.metadata = { ...existingMetadata, ...data.metadata };
      } else {
        updateData.metadata = data.metadata;
      }

      const [updated] = await tx
        .update(entries)
        .set(updateData)
        .where(eq(entries.id, entryId))
        .returning();

      if (!updated) {
        return { error: "Entry not found" };
      }

      return {
        success: true as const,
        id: updated.id,
        fullContent: updated.fullContent,
        translatedContent: updated.translatedContent,
        filteredContent: updated.filteredContent,
        rawHtml: updated.rawHtml,
        summary: updated.summary,
        annotation: updated.annotation,
        isRead: updated.isRead,
        isStarred: updated.isStarred,
        keep: updated.keep,
        thumbnailUrl: updated.thumbnailUrl,
        metadata: updated.metadata,
      };
    });
  }

  // No metadata merge needed - simple update without transaction
  const updateData: {
    fullContent?: string;
    translatedContent?: string;
    filteredContent?: string;
    rawHtml?: string;
    summary?: string;
    annotation?: string;
    isRead?: boolean;
    isStarred?: boolean;
    keep?: boolean;
    thumbnailUrl?: string;
    updatedAt: Date;
  } = {
    updatedAt: new Date(),
  };

  if (data.fullContent !== undefined) {
    updateData.fullContent = data.fullContent;
  }
  if (data.translatedContent !== undefined) {
    updateData.translatedContent = data.translatedContent;
  }
  if (data.filteredContent !== undefined) {
    updateData.filteredContent = data.filteredContent;
  }
  if (data.rawHtml !== undefined) {
    updateData.rawHtml = data.rawHtml;
  }
  if (data.summary !== undefined) {
    updateData.summary = data.summary;
  }
  if (data.annotation !== undefined) {
    updateData.annotation = data.annotation;
  }
  if (data.isRead !== undefined) {
    updateData.isRead = data.isRead;
  }
  if (data.isStarred !== undefined) {
    updateData.isStarred = data.isStarred;
  }
  if (data.keep !== undefined) {
    updateData.keep = data.keep;
  }
  if (data.thumbnailUrl !== undefined) {
    updateData.thumbnailUrl = data.thumbnailUrl;
  }

  const [updated] = await db
    .update(entries)
    .set(updateData)
    .where(eq(entries.id, entryId))
    .returning();

  if (!updated) {
    return { error: "Entry not found" };
  }

  return {
    success: true as const,
    id: updated.id,
    fullContent: updated.fullContent,
    translatedContent: updated.translatedContent,
    filteredContent: updated.filteredContent,
    rawHtml: updated.rawHtml,
    summary: updated.summary,
    annotation: updated.annotation,
    isRead: updated.isRead,
    isStarred: updated.isStarred,
    keep: updated.keep,
    thumbnailUrl: updated.thumbnailUrl,
    metadata: updated.metadata,
  };
}

/**
 * Lists entries with optional filtering and pagination.
 *
 * When feedId is specified and limit is not provided, uses the feed's
 * configured fetchLimit. Results are ordered by publishedAt descending.
 *
 * @param options - Filter and pagination options
 * @param db - Database instance (defaults to the main db)
 * @returns Array of entry objects with feed names
 */
export async function listEntries(
  options: {
    feedId?: string;
    limit?: number;
    offset?: number;
    unreadOnly?: boolean;
    hasSummary?: boolean;
  } = {},
  db: Db = defaultDb,
) {
  const { feedId, offset = 0, unreadOnly = false, hasSummary } = options;
  let { limit } = options;

  // If feedId is specified and limit is not provided, use feed's fetchLimit
  if (feedId && limit === undefined) {
    const [feed] = await db
      .select({ fetchLimit: feeds.fetchLimit })
      .from(feeds)
      .where(eq(feeds.id, feedId));

    limit = feed?.fetchLimit ?? DEFAULT_FETCH_LIMIT;
  } else {
    limit = limit ?? DEFAULT_FETCH_LIMIT;
  }

  // Ensure limit doesn't exceed max
  limit = Math.min(limit, MAX_FETCH_LIMIT);

  let query = db
    .select({
      id: entries.id,
      feedId: entries.feedId,
      feedName: feeds.name,
      title: entries.title,
      url: entries.url,
      fullContent: entries.fullContent,
      filteredContent: entries.filteredContent,
      summary: entries.summary,
      author: entries.author,
      publishedAt: entries.publishedAt,
      isRead: entries.isRead,
      isStarred: entries.isStarred,
      createdAt: entries.createdAt,
    })
    .from(entries)
    .leftJoin(feeds, eq(entries.feedId, feeds.id))
    .orderBy(desc(entries.publishedAt))
    .limit(limit)
    .offset(offset);

  if (feedId) {
    query = query.where(eq(entries.feedId, feedId)) as typeof query;
  }

  if (unreadOnly) {
    query = query.where(eq(entries.isRead, false)) as typeof query;
  }

  const result = await query;

  // Filter by hasSummary if specified (post-query filtering since drizzle
  // doesn't support empty string check easily)
  if (hasSummary !== undefined) {
    return result.filter((entry) =>
      hasSummary ? entry.summary && entry.summary.length > 0 : !entry.summary,
    );
  }

  return result;
}
