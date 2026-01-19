import { NextResponse } from "next/server";
import { db } from "@/db";
import { categories } from "@/db/schema";
import { desc } from "drizzle-orm";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:categories");

// GET /api/categories - List all categories
export async function GET() {
  try {
    const result = await db
      .select()
      .from(categories)
      .orderBy(desc(categories.createdAt));

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "failed to fetch categories");
    return NextResponse.json(
      { error: "Failed to fetch categories" },
      { status: 500 },
    );
  }
}

// POST /api/categories - Create a new category
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { name } = body;

    if (!name || typeof name !== "string") {
      return NextResponse.json({ error: "Name is required" }, { status: 400 });
    }

    const result = await db.insert(categories).values({ name }).returning();

    return NextResponse.json(result[0], { status: 201 });
  } catch (error) {
    log.error({ error }, "failed to create category");
    return NextResponse.json(
      { error: "Failed to create category" },
      { status: 500 },
    );
  }
}
