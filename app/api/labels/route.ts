import { eq } from "drizzle-orm";
import { NextRequest, NextResponse } from "next/server";

import { db } from "@/db";
import { labels } from "@/db/schema";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:labels");

/** GET /api/labels - List all labels. */
export async function GET() {
  try {
    const result = await db
      .select({
        id: labels.id,
        name: labels.name,
        color: labels.color,
      })
      .from(labels)
      .orderBy(labels.name);

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "failed to fetch labels");
    return NextResponse.json(
      { error: "Failed to fetch labels" },
      { status: 500 },
    );
  }
}

/** POST /api/labels - Create a new label. */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { name, color } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "name is required" }, { status: 400 });
    }

    if (!color || typeof color !== "string") {
      return NextResponse.json({ error: "color is required" }, { status: 400 });
    }

    // Validate color format (hex color)
    if (!/^#[0-9A-Fa-f]{6}$/.test(color)) {
      return NextResponse.json(
        { error: "color must be a valid hex color (e.g., #ff5733)" },
        { status: 400 },
      );
    }

    const [newLabel] = await db
      .insert(labels)
      .values({
        name: name.trim(),
        color: color.toLowerCase(),
      })
      .returning({
        id: labels.id,
        name: labels.name,
        color: labels.color,
      });

    return NextResponse.json(newLabel, { status: 201 });
  } catch (error) {
    log.error({ error }, "failed to create label");
    return NextResponse.json(
      { error: "Failed to create label" },
      { status: 500 },
    );
  }
}

/** PATCH /api/labels - Update a label by ID (via query param). */
export async function PATCH(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get("id");

    if (!id) {
      return NextResponse.json({ error: "id is required" }, { status: 400 });
    }

    const body = await request.json();
    const { name, color } = body;

    // Build update object with only provided fields
    const updates: { name?: string; color?: string; updatedAt: Date } = {
      updatedAt: new Date(),
    };

    if (name !== undefined) {
      if (typeof name !== "string" || !name.trim()) {
        return NextResponse.json(
          { error: "name must be a non-empty string" },
          { status: 400 },
        );
      }
      updates.name = name.trim();
    }

    if (color !== undefined) {
      if (typeof color !== "string" || !/^#[0-9A-Fa-f]{6}$/.test(color)) {
        return NextResponse.json(
          { error: "color must be a valid hex color (e.g., #ff5733)" },
          { status: 400 },
        );
      }
      updates.color = color.toLowerCase();
    }

    const [updatedLabel] = await db
      .update(labels)
      .set(updates)
      .where(eq(labels.id, id))
      .returning({
        id: labels.id,
        name: labels.name,
        color: labels.color,
      });

    if (!updatedLabel) {
      return NextResponse.json({ error: "Label not found" }, { status: 404 });
    }

    return NextResponse.json(updatedLabel);
  } catch (error) {
    log.error({ error }, "failed to update label");
    return NextResponse.json(
      { error: "Failed to update label" },
      { status: 500 },
    );
  }
}

/** DELETE /api/labels - Delete a label by ID (via query param). */
export async function DELETE(request: NextRequest) {
  try {
    const searchParams = request.nextUrl.searchParams;
    const id = searchParams.get("id");

    if (!id) {
      return NextResponse.json({ error: "id is required" }, { status: 400 });
    }

    const result = await db
      .delete(labels)
      .where(eq(labels.id, id))
      .returning({ id: labels.id });

    if (result.length === 0) {
      return NextResponse.json({ error: "Label not found" }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "failed to delete label");
    return NextResponse.json(
      { error: "Failed to delete label" },
      { status: 500 },
    );
  }
}
