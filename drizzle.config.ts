import { defineConfig } from "drizzle-kit";
import * as dotenv from "dotenv";

dotenv.config({ path: ".env" });

// Use TEST_DATABASE_URL when USE_TEST_DB=1, otherwise DATABASE_URL
const databaseUrl = process.env.USE_TEST_DB
  ? process.env.TEST_DATABASE_URL
  : process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error("DATABASE_URL is not set");
}

export default defineConfig({
  schema: "./db/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: {
    url: databaseUrl,
  },
});
