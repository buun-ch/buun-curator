import { NextRequest, NextResponse } from "next/server";
import { db } from "@/db";
import { entries, entryLabels, labels } from "@/db/schema";
import { eq, and } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:entry-labels");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/** GET /api/entries/[id]/labels - Get labels for an entry. */
export async function GET(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const result = await db
      .select({
        id: labels.id,
        name: labels.name,
        color: labels.color,
      })
      .from(entryLabels)
      .innerJoin(labels, eq(entryLabels.labelId, labels.id))
      .where(eq(entryLabels.entryId, entryId));

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "failed to fetch entry labels");
    return NextResponse.json(
      { error: "Failed to fetch entry labels" },
      { status: 500 }
    );
  }
}

/** POST /api/entries/[id]/labels - Add a label to an entry. */
export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;
    const body = await request.json();
    const { labelId } = body;

    if (!labelId || typeof labelId !== "string") {
      return NextResponse.json(
        { error: "labelId is required" },
        { status: 400 }
      );
    }

    // Verify entry exists
    const [entry] = await db
      .select({ id: entries.id })
      .from(entries)
      .where(eq(entries.id, entryId))
      .limit(1);

    if (!entry) {
      return NextResponse.json(
        { error: "Entry not found" },
        { status: 404 }
      );
    }

    // Verify label exists
    const [label] = await db
      .select({ id: labels.id, name: labels.name, color: labels.color })
      .from(labels)
      .where(eq(labels.id, labelId))
      .limit(1);

    if (!label) {
      return NextResponse.json(
        { error: "Label not found" },
        { status: 404 }
      );
    }

    // Add the label to the entry (ignore if already exists)
    await db
      .insert(entryLabels)
      .values({
        entryId,
        labelId,
      })
      .onConflictDoNothing();

    // Automatically keep the entry when a label is added
    await db
      .update(entries)
      .set({ keep: true })
      .where(eq(entries.id, entryId));

    return NextResponse.json(label, { status: 201 });
  } catch (error) {
    log.error({ error }, "failed to add label to entry");
    return NextResponse.json(
      { error: "Failed to add label to entry" },
      { status: 500 }
    );
  }
}

/** DELETE /api/entries/[id]/labels - Remove a label from an entry. */
export async function DELETE(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;
    const searchParams = request.nextUrl.searchParams;
    const labelId = searchParams.get("labelId");

    if (!labelId) {
      return NextResponse.json(
        { error: "labelId is required" },
        { status: 400 }
      );
    }

    const result = await db
      .delete(entryLabels)
      .where(
        and(
          eq(entryLabels.entryId, entryId),
          eq(entryLabels.labelId, labelId)
        )
      )
      .returning({ id: entryLabels.id });

    if (result.length === 0) {
      return NextResponse.json(
        { error: "Entry-label association not found" },
        { status: 404 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "failed to remove label from entry");
    return NextResponse.json(
      { error: "Failed to remove label from entry" },
      { status: 500 }
    );
  }
}
