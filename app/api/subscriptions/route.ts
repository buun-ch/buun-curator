import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { categories, feeds, entries } from "@/db/schema";
import { eq, sql, and } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:subscriptions");

type FilterMode = "starred" | "unread" | "all";

interface SubscriptionItem {
  id: string;
  title: string;
  type: "category" | "feed" | "special";
  count?: number;
  children?: SubscriptionItem[];
}

// GET /api/subscriptions - Get subscription tree with counts based on filter mode
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const filterMode = (searchParams.get("filterMode") as FilterMode) || "unread";
  try {
    // Get all categories
    const allCategories = await db
      .select({
        id: categories.id,
        name: categories.name,
      })
      .from(categories)
      .orderBy(categories.name);

    // Build feed count subquery based on filter mode
    const feedCountSubquery =
      filterMode === "starred"
        ? sql<number>`COALESCE(
            (SELECT COUNT(*) FROM entries
             WHERE entries.feed_id = feeds.id
             AND entries.is_starred = true), 0
          )`
        : filterMode === "unread"
          ? sql<number>`COALESCE(
              (SELECT COUNT(*) FROM entries
               WHERE entries.feed_id = feeds.id
               AND entries.is_read = false), 0
            )`
          : sql<number>`COALESCE(
              (SELECT COUNT(*) FROM entries
               WHERE entries.feed_id = feeds.id), 0
            )`;

    // Get all feeds with counts based on filter mode
    const feedsWithCounts = await db
      .select({
        id: feeds.id,
        name: feeds.name,
        categoryId: feeds.categoryId,
        count: feedCountSubquery.as("count"),
      })
      .from(feeds)
      .orderBy(feeds.name);

    // Get total count based on filter mode
    const [totalResult] = await db
      .select({
        count: sql<number>`COUNT(*)`.as("count"),
      })
      .from(entries)
      .where(
        filterMode === "starred"
          ? eq(entries.isStarred, true)
          : filterMode === "unread"
            ? eq(entries.isRead, false)
            : undefined,
      );

    // Get starred count (for "Starred" special item - always show starred count)
    const [starredResult] = await db
      .select({
        count: sql<number>`COUNT(*)`.as("count"),
      })
      .from(entries)
      .where(eq(entries.isStarred, true));

    // Build subscription tree
    const subscriptions: SubscriptionItem[] = [
      {
        id: "all",
        title: "All Entries",
        type: "special",
        count: Number(totalResult?.count || 0),
      },
    ];

    // Group feeds by category
    const categoryMap = new Map<string, typeof feedsWithCounts>();
    const uncategorizedFeeds: typeof feedsWithCounts = [];

    for (const feed of feedsWithCounts) {
      if (feed.categoryId) {
        if (!categoryMap.has(feed.categoryId)) {
          categoryMap.set(feed.categoryId, []);
        }
        categoryMap.get(feed.categoryId)!.push(feed);
      } else {
        uncategorizedFeeds.push(feed);
      }
    }

    // Add categories with their feeds
    for (const category of allCategories) {
      const categoryFeeds = categoryMap.get(category.id) || [];
      const categoryCount = categoryFeeds.reduce(
        (sum, f) => sum + Number(f.count || 0),
        0,
      );

      subscriptions.push({
        id: `category-${category.id}`,
        title: category.name,
        type: "category" as const,
        count: categoryCount,
        children: categoryFeeds.map((feed) => ({
          id: `feed-${feed.id}`,
          title: feed.name,
          type: "feed" as const,
          count: Number(feed.count || 0),
        })),
      });
    }

    // Add uncategorized feeds
    if (uncategorizedFeeds.length > 0) {
      subscriptions.push({
        id: "uncategorized",
        title: "Uncategorized",
        type: "category" as const,
        count: uncategorizedFeeds.reduce(
          (sum, f) => sum + Number(f.count || 0),
          0,
        ),
        children: uncategorizedFeeds.map((feed) => ({
          id: `feed-${feed.id}`,
          title: feed.name,
          type: "feed" as const,
          count: Number(feed.count || 0),
        })),
      });
    }

    return NextResponse.json(subscriptions);
  } catch (error) {
    log.error({ error }, "failed to fetch subscriptions");
    return NextResponse.json(
      { error: "Failed to fetch subscriptions" },
      { status: 500 },
    );
  }
}
