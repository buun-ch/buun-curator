import { eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { z } from "zod";

import { db } from "@/db";
import { entries, entryEnrichments, entryLinks } from "@/db/schema";

/** Schema for PATCH request body. */
const updateContextSchema = z.object({
  context: z.record(z.string(), z.unknown()),
});

/**
 * GET /api/entries/[id]/context
 *
 * Returns the context and enrichments for an entry.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Fetch entry with context fields
  const entry = await db
    .select({
      context: entries.context,
      contextSavedAt: entries.contextSavedAt,
      keepContext: entries.keepContext,
    })
    .from(entries)
    .where(eq(entries.id, id))
    .limit(1);

  if (entry.length === 0) {
    return NextResponse.json({ error: "Entry not found" }, { status: 404 });
  }

  // Fetch enrichments for this entry
  const enrichments = await db
    .select()
    .from(entryEnrichments)
    .where(eq(entryEnrichments.entryId, id))
    .orderBy(entryEnrichments.createdAt);

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
    context: entry[0].context,
    contextSavedAt: entry[0].contextSavedAt?.toISOString() ?? null,
    keepContext: entry[0].keepContext,
    enrichments: enrichments.map((e) => ({
      id: e.id,
      type: e.type,
      data: e.data,
      source: e.source,
      metadata: e.metadata,
      createdAt: e.createdAt.toISOString(),
      expiresAt: e.expiresAt?.toISOString() ?? null,
    })),
    links: links.map((l) => ({
      id: l.id,
      url: l.url,
      title: l.title,
      createdAt: l.createdAt.toISOString(),
    })),
  });
}

/**
 * PATCH /api/entries/[id]/context
 *
 * Updates the context for an entry.
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Parse and validate request body
  const body = await request.json();
  const parseResult = updateContextSchema.safeParse(body);

  if (!parseResult.success) {
    return NextResponse.json(
      { error: "Invalid request body", details: parseResult.error.issues },
      { status: 400 },
    );
  }

  const { context } = parseResult.data;

  // Check if entry exists
  const existing = await db
    .select({ id: entries.id })
    .from(entries)
    .where(eq(entries.id, id))
    .limit(1);

  if (existing.length === 0) {
    return NextResponse.json({ error: "Entry not found" }, { status: 404 });
  }

  // Update context and contextSavedAt
  const updated = await db
    .update(entries)
    .set({
      context,
      contextSavedAt: new Date(),
    })
    .where(eq(entries.id, id))
    .returning({
      id: entries.id,
      context: entries.context,
      contextSavedAt: entries.contextSavedAt,
    });

  return NextResponse.json({
    id: updated[0].id,
    context: updated[0].context,
    contextSavedAt: updated[0].contextSavedAt?.toISOString() ?? null,
  });
}
