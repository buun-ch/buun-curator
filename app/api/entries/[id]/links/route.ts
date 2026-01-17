import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { ulid } from "ulid";
import { z } from "zod";

import { db } from "@/db";
import { entries, entryLinks } from "@/db/schema";

/** Schema for POST request body. */
const createLinksSchema = z.object({
  links: z.array(
    z.object({
      url: z.string().min(1),
      title: z.string(),
    })
  ),
});

/**
 * POST /api/entries/[id]/links
 *
 * Saves extracted links for an entry. Replaces existing links.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  // Parse and validate request body
  const body = await request.json();
  const parseResult = createLinksSchema.safeParse(body);

  if (!parseResult.success) {
    return NextResponse.json(
      { error: "Invalid request body", details: parseResult.error.issues },
      { status: 400 }
    );
  }

  const { links } = parseResult.data;

  // Check if entry exists
  const existing = await db
    .select({ id: entries.id })
    .from(entries)
    .where(eq(entries.id, id))
    .limit(1);

  if (existing.length === 0) {
    return NextResponse.json({ error: "Entry not found" }, { status: 404 });
  }

  // Delete existing links for this entry (idempotent re-runs)
  await db.delete(entryLinks).where(eq(entryLinks.entryId, id));

  if (links.length === 0) {
    return NextResponse.json({ savedCount: 0 });
  }

  // Insert new links (use ON CONFLICT DO NOTHING for duplicates)
  const values = links.map((link) => ({
    id: ulid(),
    entryId: id,
    url: link.url,
    title: link.title,
  }));

  await db.insert(entryLinks).values(values).onConflictDoNothing();

  return NextResponse.json({ savedCount: values.length });
}

/**
 * GET /api/entries/[id]/links
 *
 * Returns all links for an entry.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  // Check if entry exists
  const existing = await db
    .select({ id: entries.id })
    .from(entries)
    .where(eq(entries.id, id))
    .limit(1);

  if (existing.length === 0) {
    return NextResponse.json({ error: "Entry not found" }, { status: 404 });
  }

  // Fetch links for this entry
  const links = await db
    .select({
      id: entryLinks.id,
      url: entryLinks.url,
      title: entryLinks.title,
      createdAt: entryLinks.createdAt,
    })
    .from(entryLinks)
    .where(eq(entryLinks.entryId, id))
    .orderBy(entryLinks.createdAt);

  return NextResponse.json({
    links: links.map((l) => ({
      id: l.id,
      url: l.url,
      title: l.title,
      createdAt: l.createdAt.toISOString(),
    })),
  });
}
