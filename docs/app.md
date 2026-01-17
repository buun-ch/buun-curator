# Next.js Application

Technical details for the Buun Curator Next.js frontend application.

## Database Management (Drizzle ORM)

This project uses [Drizzle ORM](https://orm.drizzle.team/) for database management with PostgreSQL.

### Directory Structure

```text
db/
  schema.ts    # Database schema definitions
  index.ts     # Database client initialization
drizzle/
  *.sql        # Generated migration files
  meta/        # Migration metadata
drizzle.config.ts  # Drizzle Kit configuration
```

### Schema

The database schema is defined in `db/schema.ts`:

- **categories** - Feed categories
    - `id`, `name`, `created_at`, `updated_at`
- **feeds** - RSS/Atom feed subscriptions
    - `id`, `name`, `url`, `site_url`, `category_id`, `type`, `options`, `etag`, `last_modified`, `checked_at`, `created_at`, `updated_at`
- **entries** - Feed entries
    - `id`, `feed_id`, `title`, `url`, `feed_content`, `full_content`, `summary`, `author`, `published_at`, `is_read`, `is_starred`, `metadata`, `created_at`, `updated_at`
    - `feed_content`: HTML content from RSS/Atom feed
    - `full_content`: Markdown content fetched by crawler (e.g., Crawl4AI)
    - `summary`: AI-generated summary
    - Unique index on `url` to prevent duplicates

### Commands

| Command            | Description                                                  |
| ------------------ | ------------------------------------------------------------ |
| `bun db:generate` | Generate migration files from schema changes                 |
| `bun db:migrate`  | Run pending migrations                                       |
| `bun db:push`     | Push schema changes directly to the database (development)   |
| `bun db:studio`   | Open Drizzle Studio (database GUI)                           |

### Workflow

#### Development (Quick iteration)

Use `db:push` for rapid development without creating migration files:

```bash
bun db:push
```

This directly synchronizes your schema with the database. Good for prototyping.

#### Production (Version-controlled migrations)

1. Make changes to `db/schema.ts`
2. Generate a migration:

   ```bash
   bun db:generate
   ```

3. Review the generated SQL in `drizzle/` directory
4. Apply the migration:

   ```bash
   bun db:migrate
   ```

### Using the Database Client

Import the database client in your code:

```typescript
import { db } from "@/db";
import { categories, feeds } from "@/db/schema";
import { eq } from "drizzle-orm";

// Select all categories
const allCategories = await db.select().from(categories);

// Insert a new feed
await db.insert(feeds).values({
  name: "Hacker News",
  url: "https://news.ycombinator.com/rss",
  categoryId: 1,
});

// Query with conditions
const techFeeds = await db
  .select()
  .from(feeds)
  .where(eq(feeds.categoryId, 1));
```

### Drizzle Studio

Launch the visual database browser:

```bash
bun db:studio
```

This opens a web UI at `https://local.drizzle.studio` where you can browse and edit data.

## API

Buun Curator provides two API interfaces:

### REST API

Standard JSON API for programmatic access:

```text
GET    /api/feeds              # List all feeds
GET    /api/feeds/:id          # Get feed details
POST   /api/feeds/:id/checked  # Update feed check timestamp
GET    /api/entries            # List entries with filtering
POST   /api/entries            # Create new entry
GET    /api/entries/:id        # Get entry details
PATCH  /api/entries/:id        # Update entry content/summary
GET    /api/settings           # Get application settings
```

## Testing

### Setup

Create a test database `buun_curator_test` and run migrations:

```bash
bun db:migrate:test
```

### Commands

| Command         | Description              |
| --------------- | ------------------------ |
| `bun test`     | Run tests in watch mode  |
| `bun test:run` | Run tests once           |

## Client-Side State Management

For React Query cache keys and UI action → query flows, see [Query and Cache Design](./query-and-cache.md).
