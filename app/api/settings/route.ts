import { NextResponse } from "next/server";
import { db } from "@/db";
import { appSettings } from "@/db/schema";
import { eq } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:settings");

// GET /api/settings - Get app settings (create default if not exists)
export async function GET() {
  try {
    const result = await db.select().from(appSettings).limit(1);

    if (result.length === 0) {
      // Create default settings
      const newSettings = await db
        .insert(appSettings)
        .values({ targetLanguage: null })
        .returning();
      return NextResponse.json(newSettings[0]);
    }

    return NextResponse.json(result[0]);
  } catch (error) {
    log.error({ error }, "failed to fetch settings");
    return NextResponse.json(
      { error: "Failed to fetch settings" },
      { status: 500 },
    );
  }
}

// PATCH /api/settings - Update app settings
export async function PATCH(request: Request) {
  try {
    const body = await request.json();
    const { targetLanguage } = body;

    // Get existing settings or create new
    let existing = await db.select().from(appSettings).limit(1);

    if (existing.length === 0) {
      const newSettings = await db
        .insert(appSettings)
        .values({
          targetLanguage: targetLanguage === "" ? null : targetLanguage,
        })
        .returning();
      return NextResponse.json(newSettings[0]);
    }

    // Update existing settings
    const updated = await db
      .update(appSettings)
      .set({
        targetLanguage: targetLanguage === "" ? null : targetLanguage,
        updatedAt: new Date(),
      })
      .where(eq(appSettings.id, existing[0].id))
      .returning();

    return NextResponse.json(updated[0]);
  } catch (error) {
    log.error({ error }, "failed to update settings");
    return NextResponse.json(
      { error: "Failed to update settings" },
      { status: 500 },
    );
  }
}
