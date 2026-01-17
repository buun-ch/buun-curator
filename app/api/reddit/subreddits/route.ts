import { NextResponse } from "next/server";
import { db } from "@/db";
import { redditSubreddits } from "@/db/schema";
import { eq } from "drizzle-orm";

import { checkRedditEnabled } from "@/lib/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:reddit:subreddits");

// GET /api/reddit/subreddits - Get all favorite subreddits
export async function GET() {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  try {
    const subreddits = await db
      .select({
        id: redditSubreddits.id,
        name: redditSubreddits.name,
        minScore: redditSubreddits.minScore,
        createdAt: redditSubreddits.createdAt,
      })
      .from(redditSubreddits)
      .orderBy(redditSubreddits.name);

    return NextResponse.json(subreddits);
  } catch (error) {
    log.error({ error }, "Failed to fetch subreddits");
    return NextResponse.json(
      { error: "Failed to fetch subreddits" },
      { status: 500 }
    );
  }
}

// POST /api/reddit/subreddits - Add a new favorite subreddit
export async function POST(request: Request) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  try {
    const body = await request.json();
    const { name } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json(
        { error: "Subreddit name is required" },
        { status: 400 }
      );
    }

    // Normalize name (remove r/ prefix if present, lowercase)
    const normalizedName = name.replace(/^r\//i, "").toLowerCase().trim();

    if (!normalizedName) {
      return NextResponse.json(
        { error: "Invalid subreddit name" },
        { status: 400 }
      );
    }

    // Check if already exists
    const existing = await db
      .select({ id: redditSubreddits.id })
      .from(redditSubreddits)
      .where(eq(redditSubreddits.name, normalizedName))
      .limit(1);

    if (existing.length > 0) {
      return NextResponse.json(
        { error: "Subreddit already in favorites" },
        { status: 409 }
      );
    }

    // Insert new subreddit
    const [inserted] = await db
      .insert(redditSubreddits)
      .values({
        name: normalizedName,
      })
      .returning({
        id: redditSubreddits.id,
        name: redditSubreddits.name,
        minScore: redditSubreddits.minScore,
        createdAt: redditSubreddits.createdAt,
      });

    return NextResponse.json(inserted, { status: 201 });
  } catch (error) {
    log.error({ error }, "Failed to add subreddit");
    return NextResponse.json(
      { error: "Failed to add subreddit" },
      { status: 500 }
    );
  }
}
