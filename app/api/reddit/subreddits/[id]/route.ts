import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";

import { db } from "@/db";
import { redditSubreddits } from "@/db/schema";
import { checkRedditEnabled } from "@/lib/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:reddit:subreddits:id");

// DELETE /api/reddit/subreddits/[id] - Remove a favorite subreddit
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  const { id } = await params;

  try {
    const deleted = await db
      .delete(redditSubreddits)
      .where(eq(redditSubreddits.id, id))
      .returning({ id: redditSubreddits.id });

    if (deleted.length === 0) {
      return NextResponse.json(
        { error: "Subreddit not found" },
        { status: 404 },
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "Failed to delete subreddit");
    return NextResponse.json(
      { error: "Failed to delete subreddit" },
      { status: 500 },
    );
  }
}

// PATCH /api/reddit/subreddits/[id] - Update subreddit settings (e.g., minScore)
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  const { id } = await params;

  try {
    const body = await request.json();
    const { minScore } = body;

    const updateData: { minScore?: number; updatedAt: Date } = {
      updatedAt: new Date(),
    };

    if (typeof minScore === "number" && minScore >= 0) {
      updateData.minScore = minScore;
    }

    const [updated] = await db
      .update(redditSubreddits)
      .set(updateData)
      .where(eq(redditSubreddits.id, id))
      .returning({
        id: redditSubreddits.id,
        name: redditSubreddits.name,
        minScore: redditSubreddits.minScore,
      });

    if (!updated) {
      return NextResponse.json(
        { error: "Subreddit not found" },
        { status: 404 },
      );
    }

    return NextResponse.json(updated);
  } catch (error) {
    log.error({ error }, "Failed to update subreddit");
    return NextResponse.json(
      { error: "Failed to update subreddit" },
      { status: 500 },
    );
  }
}
