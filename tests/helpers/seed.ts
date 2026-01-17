import { testDb, schema } from "../setup";

export interface SeedData {
  categories: (typeof schema.categories.$inferSelect)[];
  feeds: (typeof schema.feeds.$inferSelect)[];
  entries: (typeof schema.entries.$inferSelect)[];
}

// Seed categories
export async function seedCategories(
  data: { name: string }[]
): Promise<(typeof schema.categories.$inferSelect)[]> {
  if (data.length === 0) return [];
  return testDb.insert(schema.categories).values(data).returning();
}

// Seed feeds
export async function seedFeeds(
  data: {
    name: string;
    url: string;
    siteUrl?: string;
    categoryId?: string;
    type?: string;
  }[]
): Promise<(typeof schema.feeds.$inferSelect)[]> {
  if (data.length === 0) return [];
  return testDb.insert(schema.feeds).values(data).returning();
}

// Seed entries
export async function seedEntries(
  data: {
    feedId: string;
    title: string;
    url: string;
    feedContent?: string;
    fullContent?: string;
    summary?: string;
    author?: string;
    publishedAt?: Date;
    isRead?: boolean;
    isStarred?: boolean;
  }[]
): Promise<(typeof schema.entries.$inferSelect)[]> {
  if (data.length === 0) return [];
  return testDb.insert(schema.entries).values(data).returning();
}

// Seed all with default test data
export async function seedAll(): Promise<SeedData> {
  const categories = await seedCategories([
    { name: "Tech" },
    { name: "News" },
  ]);

  const feeds = await seedFeeds([
    {
      name: "Hacker News",
      url: "https://news.ycombinator.com/rss",
      siteUrl: "https://news.ycombinator.com",
      categoryId: categories[0].id,
      type: "rss",
    },
    {
      name: "TechCrunch",
      url: "https://techcrunch.com/feed/",
      siteUrl: "https://techcrunch.com",
      categoryId: categories[0].id,
      type: "rss",
    },
    {
      name: "BBC News",
      url: "https://feeds.bbci.co.uk/news/rss.xml",
      siteUrl: "https://www.bbc.com/news",
      categoryId: categories[1].id,
      type: "rss",
    },
  ]);

  const entries = await seedEntries([
    {
      feedId: feeds[0].id,
      title: "First HN Entry",
      url: "https://example.com/article1",
      summary: "This is a summary of the first article",
      author: "author1",
      publishedAt: new Date("2024-01-01T10:00:00Z"),
      isRead: false,
      isStarred: false,
    },
    {
      feedId: feeds[0].id,
      title: "Second HN Entry",
      url: "https://example.com/article2",
      summary: "This is a summary of the second article",
      author: "author2",
      publishedAt: new Date("2024-01-02T10:00:00Z"),
      isRead: true,
      isStarred: true,
    },
    {
      feedId: feeds[1].id,
      title: "TechCrunch Entry",
      url: "https://example.com/article3",
      summary: "TechCrunch summary",
      publishedAt: new Date("2024-01-03T10:00:00Z"),
      isRead: false,
      isStarred: false,
    },
  ]);

  return { categories, feeds, entries };
}
