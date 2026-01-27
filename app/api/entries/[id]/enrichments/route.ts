import { and, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { ulid } from "ulid";
import { z } from "zod";

import { db } from "@/db";
import { entries, entryEnrichments } from "@/db/schema";

/** Schema for DELETE request body. */
const deleteEnrichmentSchema = z.object({
  type: z.string().min(1),
  source: z.string().min(1).optional(), // Optional: if omitted, deletes all enrichments of this type
});

/** Schema for POST request body. */
const createEnrichmentSchema = z.object({
  type: z.string().min(1),
  data: z.record(z.string(), z.unknown()),
  source: z.string().optional(),
  metadata: z.record(z.string(), z.unknown()).optional(),
  expiresAt: z.iso.datetime().optional(),
});

/**
 * POST /api/entries/[id]/enrichments
 *
 * Creates a new enrichment for an entry.
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Parse and validate request body
  const body = await request.json();
  const parseResult = createEnrichmentSchema.safeParse(body);

  if (!parseResult.success) {
    return NextResponse.json(
      { error: "Invalid request body", details: parseResult.error.issues },
      { status: 400 },
    );
  }

  const { type, data, source, metadata, expiresAt } = parseResult.data;

  // Check if entry exists
  const existing = await db
    .select({ id: entries.id })
    .from(entries)
    .where(eq(entries.id, id))
    .limit(1);

  if (existing.length === 0) {
    return NextResponse.json({ error: "Entry not found" }, { status: 404 });
  }

  // Delete existing enrichments of the same type and source (for idempotent re-runs)
  // When source is provided, delete by (entryId, type, source) for per-URL updates
  // When source is not provided, delete by (entryId, type) for bulk updates
  const deleteConditions = source
    ? and(
        eq(entryEnrichments.entryId, id),
        eq(entryEnrichments.type, type),
        eq(entryEnrichments.source, source),
      )
    : and(eq(entryEnrichments.entryId, id), eq(entryEnrichments.type, type));

  await db.delete(entryEnrichments).where(deleteConditions);

  // Create enrichment
  const enrichmentId = ulid();
  const created = await db
    .insert(entryEnrichments)
    .values({
      id: enrichmentId,
      entryId: id,
      type,
      data,
      source: source ?? null,
      metadata: metadata ?? null,
      expiresAt: expiresAt ? new Date(expiresAt) : null,
    })
    .returning();

  return NextResponse.json({
    id: created[0].id,
    entryId: created[0].entryId,
    type: created[0].type,
    data: created[0].data,
    source: created[0].source,
    metadata: created[0].metadata,
    createdAt: created[0].createdAt.toISOString(),
    expiresAt: created[0].expiresAt?.toISOString() ?? null,
  });
}

/**
 * DELETE /api/entries/[id]/enrichments
 *
 * Deletes enrichments for an entry by type and optionally source.
 * If source is omitted, deletes all enrichments of the given type.
 */
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;

  // Parse and validate request body
  const body = await request.json();
  const parseResult = deleteEnrichmentSchema.safeParse(body);

  if (!parseResult.success) {
    return NextResponse.json(
      { error: "Invalid request body", details: parseResult.error.issues },
      { status: 400 },
    );
  }

  const { type, source } = parseResult.data;

  // Build delete conditions: if source is provided, delete by (entryId, type, source)
  // otherwise delete all enrichments of this type for the entry
  const deleteConditions = source
    ? and(
        eq(entryEnrichments.entryId, id),
        eq(entryEnrichments.type, type),
        eq(entryEnrichments.source, source),
      )
    : and(eq(entryEnrichments.entryId, id), eq(entryEnrichments.type, type));

  // Delete the enrichment(s)
  const deleted = await db
    .delete(entryEnrichments)
    .where(deleteConditions)
    .returning({ id: entryEnrichments.id });

  if (deleted.length === 0) {
    return NextResponse.json(
      { error: "Enrichment not found", deleted: false },
      { status: 404 },
    );
  }

  return NextResponse.json({
    deleted: true,
    deletedCount: deleted.length,
    deletedIds: deleted.map((d) => d.id),
  });
}
