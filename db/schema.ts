import { relations } from "drizzle-orm";
import {
  boolean,
  char,
  customType,
  index,
  integer,
  json,
  pgTable,
  text,
  timestamp,
  uniqueIndex,
} from "drizzle-orm/pg-core";
import { ulid } from "ulid";

// Custom type for pgvector's vector type
const vector = customType<{ data: number[]; driverData: string }>({
  dataType() {
    return "vector(768)";
  },
  toDriver(value: number[]): string {
    return `[${value.join(",")}]`;
  },
  fromDriver(value: string): number[] {
    // Parse "[0.1,0.2,...]" format
    const match = value.match(/\[(.*)\]/);
    if (!match) return [];
    return match[1].split(",").map(Number);
  },
});

// ULID helper - generates new ULID for default values
const ulidDefault = () => ulid();

export const categories = pgTable("categories", {
  id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
  name: text("name").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});

export const feeds = pgTable("feeds", {
  id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
  name: text("name").notNull(),
  url: text("url").notNull(),
  siteUrl: text("site_url"),
  categoryId: char("category_id", { length: 26 }).references(
    () => categories.id,
    {
      onDelete: "set null",
    },
  ),
  type: text("type"),
  fetchContent: boolean("fetch_content").default(true).notNull(),
  fetchLimit: integer("fetch_limit").default(20).notNull(),
  options: json("options"), // Contains extractionRules only
  etag: text("etag"),
  lastModified: text("last_modified"),
  checkedAt: timestamp("checked_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});

export const entries = pgTable(
  "entries",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    feedId: char("feed_id", { length: 26 })
      .references(() => feeds.id, { onDelete: "cascade" })
      .notNull(),
    title: text("title").notNull(),
    url: text("url").notNull(),
    feedContent: text("feed_content").default("").notNull(),
    fullContent: text("full_content").default("").notNull(),
    translatedContent: text("translated_content").default("").notNull(),
    filteredContent: text("filtered_content").default("").notNull(),
    rawHtml: text("raw_html").default("").notNull(),
    summary: text("summary").default("").notNull(),
    author: text("author"),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    isRead: boolean("is_read").default(false).notNull(),
    isStarred: boolean("is_starred").default(false).notNull(),
    keep: boolean("keep").default(false).notNull(), // true = preserved from auto-cleanup
    thumbnailUrl: text("thumbnail_url"),
    metadata: json("metadata"),
    context: json("context"),
    contextSavedAt: timestamp("context_saved_at", { withTimezone: true }),
    keepContext: boolean("keep_context").default(false).notNull(), // false = subject to auto-cleanup
    graphAddedAt: timestamp("graph_added_at", { withTimezone: true }), // null = not added to knowledge graph
    embedding: vector("embedding"), // 768-dim vector for recommendation
    annotation: text("annotation").default("").notNull(), // User annotation (Markdown)
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [uniqueIndex("entries_url_idx").on(table.url)],
);

// Entry enrichments: additional context from external sources (web search, etc.)
export const entryEnrichments = pgTable(
  "entry_enrichments",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    entryId: char("entry_id", { length: 26 })
      .references(() => entries.id, { onDelete: "cascade" })
      .notNull(),
    type: text("type").notNull(), // 'github', 'web_search', etc.
    data: json("data"), // Enriched context data
    source: text("source"), // Source URL or identifier
    metadata: json("metadata"), // Search parameters, config, etc.
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }), // null = no expiration
  },
  (table) => [index("entry_enrichments_entry_id_idx").on(table.entryId)],
);

// Entry links: URL candidates extracted from article content
export const entryLinks = pgTable(
  "entry_links",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    entryId: char("entry_id", { length: 26 })
      .references(() => entries.id, { onDelete: "cascade" })
      .notNull(),
    url: text("url").notNull(), // Normalized URL
    title: text("title").notNull(), // Link text
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("entry_links_entry_id_idx").on(table.entryId),
    uniqueIndex("entry_links_entry_url_title_idx").on(
      table.entryId,
      table.url,
      table.title,
    ),
  ],
);

export const appSettings = pgTable("app_settings", {
  id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
  targetLanguage: text("target_language"),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});

// Reddit: Favorite subreddits
export const redditSubreddits = pgTable(
  "reddit_subreddits",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    name: text("name").notNull(), // subreddit name (e.g., "programming")
    minScore: integer("min_score").default(0).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [uniqueIndex("reddit_subreddits_name_idx").on(table.name)],
);

// Reddit: Starred posts
export const redditPosts = pgTable(
  "reddit_posts",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    postId: text("post_id").notNull(), // Reddit post ID
    subreddit: text("subreddit").notNull(), // subreddit name
    isStarred: boolean("is_starred").default(false).notNull(),
    isRead: boolean("is_read").default(false).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [uniqueIndex("reddit_posts_post_id_idx").on(table.postId)],
);

// =============================================================================
// Labels for Entries
// =============================================================================

export const labels = pgTable(
  "labels",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    name: text("name").notNull(),
    color: text("color").notNull(), // hex color code (e.g., "#ff5733")
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [uniqueIndex("labels_name_idx").on(table.name)],
);

export const entryLabels = pgTable(
  "entry_labels",
  {
    id: char("id", { length: 26 }).primaryKey().$defaultFn(ulidDefault),
    entryId: char("entry_id", { length: 26 })
      .references(() => entries.id, { onDelete: "cascade" })
      .notNull(),
    labelId: char("label_id", { length: 26 })
      .references(() => labels.id, { onDelete: "cascade" })
      .notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [
    index("entry_labels_entry_id_idx").on(table.entryId),
    index("entry_labels_label_id_idx").on(table.labelId),
    uniqueIndex("entry_labels_entry_label_idx").on(
      table.entryId,
      table.labelId,
    ),
  ],
);

// =============================================================================
// Better Auth Tables
// =============================================================================

export const user = pgTable("user", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  email: text("email").notNull().unique(),
  emailVerified: boolean("email_verified").default(false).notNull(),
  image: text("image"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .defaultNow()
    .notNull(),
});

export const session = pgTable(
  "session",
  {
    id: text("id").primaryKey(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    token: text("token").notNull().unique(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    ipAddress: text("ip_address"),
    userAgent: text("user_agent"),
    userId: text("user_id")
      .notNull()
      .references(() => user.id, { onDelete: "cascade" }),
  },
  (table) => [index("session_user_id_idx").on(table.userId)],
);

export const account = pgTable(
  "account",
  {
    id: text("id").primaryKey(),
    accountId: text("account_id").notNull(),
    providerId: text("provider_id").notNull(),
    userId: text("user_id")
      .notNull()
      .references(() => user.id, { onDelete: "cascade" }),
    accessToken: text("access_token"),
    refreshToken: text("refresh_token"),
    idToken: text("id_token"),
    accessTokenExpiresAt: timestamp("access_token_expires_at", {
      withTimezone: true,
    }),
    refreshTokenExpiresAt: timestamp("refresh_token_expires_at", {
      withTimezone: true,
    }),
    scope: text("scope"),
    password: text("password"),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [index("account_user_id_idx").on(table.userId)],
);

export const verification = pgTable(
  "verification",
  {
    id: text("id").primaryKey(),
    identifier: text("identifier").notNull(),
    value: text("value").notNull(),
    expiresAt: timestamp("expires_at", { withTimezone: true }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .defaultNow()
      .notNull(),
  },
  (table) => [index("verification_identifier_idx").on(table.identifier)],
);

// Better Auth Relations
export const userRelations = relations(user, ({ many }) => ({
  sessions: many(session),
  accounts: many(account),
}));

export const sessionRelations = relations(session, ({ one }) => ({
  user: one(user, {
    fields: [session.userId],
    references: [user.id],
  }),
}));

export const accountRelations = relations(account, ({ one }) => ({
  user: one(user, {
    fields: [account.userId],
    references: [user.id],
  }),
}));

// Label Relations
export const labelRelations = relations(labels, ({ many }) => ({
  entryLabels: many(entryLabels),
}));

export const entryLabelRelations = relations(entryLabels, ({ one }) => ({
  entry: one(entries, {
    fields: [entryLabels.entryId],
    references: [entries.id],
  }),
  label: one(labels, {
    fields: [entryLabels.labelId],
    references: [labels.id],
  }),
}));
