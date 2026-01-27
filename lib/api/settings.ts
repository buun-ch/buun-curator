/**
 * Application settings operations.
 *
 * @module lib/api/settings
 */

import { db as defaultDb } from "@/db";
import { appSettings } from "@/db/schema";

import type { Db } from "./types";

/** Application-wide settings stored in the database. */
export interface AppSettings {
  /** Unique identifier for the settings record. */
  id: string;
  /** Target language for AI-generated summaries (ISO code or null for original). */
  targetLanguage: string | null;
  /** Timestamp of last settings update. */
  updatedAt: Date;
}

/**
 * Gets application settings, creating defaults if none exist.
 *
 * @param database - Database instance (defaults to the main db)
 * @returns The application settings
 */
export async function getSettings(
  database: Db = defaultDb,
): Promise<AppSettings> {
  const result = await database.select().from(appSettings).limit(1);

  if (result.length === 0) {
    // Create default settings
    const newSettings = await database
      .insert(appSettings)
      .values({ targetLanguage: null })
      .returning();
    return newSettings[0];
  }

  return result[0];
}
