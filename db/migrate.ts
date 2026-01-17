/**
 * Database migration script for production deployment.
 *
 * Uses drizzle-orm's programmatic migration API instead of drizzle-kit CLI.
 * This script is compiled to JavaScript and included in the Docker image.
 *
 * @module db/migrate
 */

import { drizzle } from "drizzle-orm/node-postgres";
import { migrate } from "drizzle-orm/node-postgres/migrator";
import { Pool } from "pg";

async function runMigrations() {
  const databaseUrl = process.env.DATABASE_URL;

  if (!databaseUrl) {
    console.error("DATABASE_URL is not set");
    process.exit(1);
  }

  console.log("Connecting to database...");

  const pool = new Pool({
    connectionString: databaseUrl,
    max: 1,
    connectionTimeoutMillis: 10000,
  });

  const db = drizzle(pool);

  console.log("Running migrations...");

  try {
    await migrate(db, { migrationsFolder: "./drizzle" });
    console.log("Migrations completed successfully");
  } catch (error) {
    console.error("Migration failed:", error);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

runMigrations();
