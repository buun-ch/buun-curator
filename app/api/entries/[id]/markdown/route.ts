import { NextRequest, NextResponse } from "next/server";
import TurndownService from "turndown";

import { db } from "@/db";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entries:markdown");
import { entries } from "@/db/schema";
import { eq } from "drizzle-orm";

interface RouteParams {
  params: Promise<{ id: string }>;
}

/**
 * Sanitizes a string for use as a filename.
 */
function sanitizeFilename(title: string): string {
  return title
    .replace(/[/\\?%*:|"<>]/g, "-")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 100);
}

/**
 * GET /api/entries/[id]/markdown - Get entry content as Markdown.
 *
 * Returns the entry content formatted as Markdown with title as H1 heading.
 * Uses filteredContent if available, otherwise converts feedContent from HTML.
 */
export async function GET(_request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const [entry] = await db
      .select({
        title: entries.title,
        feedContent: entries.feedContent,
        filteredContent: entries.filteredContent,
      })
      .from(entries)
      .where(eq(entries.id, entryId));

    if (!entry) {
      return NextResponse.json({ error: "Entry not found" }, { status: 404 });
    }

    // Determine content: prefer filteredContent (Markdown), fallback to feedContent (HTML)
    let bodyContent: string;
    if (entry.filteredContent && entry.filteredContent.length > 0) {
      bodyContent = entry.filteredContent;
    } else if (entry.feedContent && entry.feedContent.length > 0) {
      const turndown = new TurndownService({
        headingStyle: "atx",
        codeBlockStyle: "fenced",
      });
      bodyContent = turndown.turndown(entry.feedContent);
    } else {
      bodyContent = "";
    }

    // Combine title and content
    const markdown = `# ${entry.title}\n\n${bodyContent}`;
    const filename = `${sanitizeFilename(entry.title || "entry")}.md`;
    const encodedFilename = encodeURIComponent(filename);

    return new NextResponse(markdown, {
      status: 200,
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename*=UTF-8''${encodedFilename}`,
      },
    });
  } catch (error) {
    log.error({ error }, "Failed to generate markdown");
    return NextResponse.json(
      { error: "Failed to generate markdown" },
      { status: 500 }
    );
  }
}
