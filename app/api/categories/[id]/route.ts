import { NextResponse } from "next/server";
import { db } from "@/db";
import { categories } from "@/db/schema";
import { eq } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:categories");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// GET /api/categories/[id] - Get a single category
export async function GET(request: Request, { params }: RouteParams) {
  try {
    const { id: categoryId } = await params;

    const result = await db
      .select()
      .from(categories)
      .where(eq(categories.id, categoryId))
      .limit(1);

    if (result.length === 0) {
      return NextResponse.json({ error: "Category not found" }, { status: 404 });
    }

    return NextResponse.json(result[0]);
  } catch (error) {
    log.error({ error }, "failed to fetch category");
    return NextResponse.json(
      { error: "Failed to fetch category" },
      { status: 500 }
    );
  }
}

// PATCH /api/categories/[id] - Update a category
export async function PATCH(request: Request, { params }: RouteParams) {
  try {
    const { id: categoryId } = await params;

    const body = await request.json();
    const { name } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "Name is required" }, { status: 400 });
    }

    const result = await db
      .update(categories)
      .set({ name, updatedAt: new Date() })
      .where(eq(categories.id, categoryId))
      .returning();

    if (result.length === 0) {
      return NextResponse.json({ error: "Category not found" }, { status: 404 });
    }

    return NextResponse.json(result[0]);
  } catch (error) {
    log.error({ error }, "failed to update category");
    return NextResponse.json(
      { error: "Failed to update category" },
      { status: 500 }
    );
  }
}

// DELETE /api/categories/[id] - Delete a category
export async function DELETE(request: Request, { params }: RouteParams) {
  try {
    const { id: categoryId } = await params;

    const result = await db
      .delete(categories)
      .where(eq(categories.id, categoryId))
      .returning();

    if (result.length === 0) {
      return NextResponse.json({ error: "Category not found" }, { status: 404 });
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "failed to delete category");
    return NextResponse.json(
      { error: "Failed to delete category" },
      { status: 500 }
    );
  }
}
