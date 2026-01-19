/**
 * Feed-related database operations.
 *
 * @module lib/api/feeds
 */

import { db as defaultDb } from "@/db";
import { feeds, categories } from "@/db/schema";
import { eq } from "drizzle-orm";
import type { Db, ExtractionRule, FeedOptions, ErrorResult } from "./types";

/**
 * Lists all feeds with their category information.
 *
 * @param db - Database instance (defaults to the main db)
 * @returns Array of feed objects with category names
 */
export async function listFeeds(db: Db = defaultDb) {
  return db
    .select({
      id: feeds.id,
      name: feeds.name,
      url: feeds.url,
      siteUrl: feeds.siteUrl,
      type: feeds.type,
      categoryId: feeds.categoryId,
      categoryName: categories.name,
      options: feeds.options,
      checkedAt: feeds.checkedAt,
    })
    .from(feeds)
    .leftJoin(categories, eq(feeds.categoryId, categories.id));
}

/**
 * Gets a specific feed by ID with full details including cache headers.
 *
 * @param feedId - The feed's unique identifier
 * @param db - Database instance (defaults to the main db)
 * @returns The feed object or null if not found
 */
export async function getFeed(feedId: string, db: Db = defaultDb) {
  const [feed] = await db
    .select({
      id: feeds.id,
      name: feeds.name,
      url: feeds.url,
      siteUrl: feeds.siteUrl,
      type: feeds.type,
      categoryId: feeds.categoryId,
      categoryName: categories.name,
      options: feeds.options,
      etag: feeds.etag,
      lastModified: feeds.lastModified,
      checkedAt: feeds.checkedAt,
      createdAt: feeds.createdAt,
      updatedAt: feeds.updatedAt,
    })
    .from(feeds)
    .leftJoin(categories, eq(feeds.categoryId, categories.id))
    .where(eq(feeds.id, feedId));

  return feed || null;
}

/**
 * Updates a feed's checkedAt timestamp and HTTP cache headers.
 *
 * Called after checking a feed for new entries to record the check time
 * and store ETag/Last-Modified for conditional requests.
 *
 * @param feedId - The feed's unique identifier
 * @param options - Cache header values (empty string to unset)
 * @param db - Database instance (defaults to the main db)
 * @returns Success result with updated values, or error if feed not found
 */
export async function updateFeedChecked(
  feedId: string,
  options: {
    etag?: string;
    lastModified?: string;
  } = {},
  db: Db = defaultDb,
) {
  const updateData: {
    checkedAt: Date;
    updatedAt: Date;
    etag?: string;
    lastModified?: string;
  } = {
    checkedAt: new Date(),
    updatedAt: new Date(),
  };

  if (options.etag !== undefined) {
    updateData.etag = options.etag;
  }
  if (options.lastModified !== undefined) {
    updateData.lastModified = options.lastModified;
  }

  const [updated] = await db
    .update(feeds)
    .set(updateData)
    .where(eq(feeds.id, feedId))
    .returning();

  if (!updated) {
    return { error: "Feed not found" };
  }

  return {
    success: true as const,
    checkedAt: updated.checkedAt,
    etag: updated.etag || "",
    lastModified: updated.lastModified || "",
  };
}

/**
 * Saves a content extraction rule to a feed's options.
 *
 * Extraction rules define CSS selectors or XPath expressions to exclude
 * unwanted content (ads, navigation, etc.) when fetching entry content.
 *
 * @param feedId - The feed's unique identifier
 * @param rule - The extraction rule to add
 * @param db - Database instance (defaults to the main db)
 * @returns Success result with the added rule, or error if feed not found or rule exists
 */
export async function saveExtractionRule(
  feedId: string,
  rule: {
    type: "css_selector" | "xpath";
    value: string;
    description?: string;
  },
  db: Db = defaultDb,
): Promise<
  | ErrorResult
  | {
      success: true;
      feedId: string;
      addedRule: ExtractionRule;
      totalRules: number;
    }
> {
  // Get current feed options
  const [feed] = await db
    .select({
      id: feeds.id,
      options: feeds.options,
    })
    .from(feeds)
    .where(eq(feeds.id, feedId));

  if (!feed) {
    return { error: "Feed not found" };
  }

  // Parse existing options or create new
  const currentOptions = (feed.options as FeedOptions) || {};
  const existingRules = currentOptions.extractionRules || [];

  // Check for duplicate
  const isDuplicate = existingRules.some(
    (r) => r.type === rule.type && r.value === rule.value,
  );

  if (isDuplicate) {
    return {
      error: "Rule already exists",
      existingRules,
    };
  }

  // Add new rule
  const newRule: ExtractionRule = {
    type: rule.type,
    value: rule.value,
    description: rule.description,
    createdAt: new Date().toISOString(),
  };

  const updatedOptions: FeedOptions = {
    ...currentOptions,
    extractionRules: [...existingRules, newRule],
  };

  // Update feed
  const [updated] = await db
    .update(feeds)
    .set({
      options: updatedOptions,
      updatedAt: new Date(),
    })
    .where(eq(feeds.id, feedId))
    .returning();

  return {
    success: true,
    feedId: updated.id,
    addedRule: newRule,
    totalRules: updatedOptions.extractionRules?.length || 0,
  };
}
