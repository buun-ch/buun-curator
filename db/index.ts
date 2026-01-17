import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL is not set");
}

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20, // Increase from default 10 to handle concurrent MCP requests
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 10000, // 10 second timeout for acquiring connection
});

export const db = drizzle(pool, { schema });
