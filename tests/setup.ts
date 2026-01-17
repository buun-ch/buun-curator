import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import { sql } from "drizzle-orm";
import { config } from "dotenv";
import * as schema from "@/db/schema";

// Load .env to get TEST_DATABASE_URL
config({ path: ".env" });

const DATABASE_URL = process.env.TEST_DATABASE_URL;

if (!DATABASE_URL) {
  throw new Error("TEST_DATABASE_URL is not set in .env");
}

// Create test pool and db instance
const testPool = new Pool({
  connectionString: DATABASE_URL,
});

export const testDb = drizzle(testPool, { schema });

// Clean all tables
export async function cleanDatabase() {
  await testDb.execute(
    sql`TRUNCATE entries, feeds, categories RESTART IDENTITY CASCADE`
  );
}

// Close the database connection pool
export async function closeDatabase() {
  await testPool.end();
}

// Log database URL (masked)
export function logDatabaseUrl() {
  const maskedUrl = DATABASE_URL!.replace(/:([^@]+)@/, ":***@");
  console.log(`Setting up test database: ${maskedUrl}`);
}

// Export for use in tests
export { schema };
