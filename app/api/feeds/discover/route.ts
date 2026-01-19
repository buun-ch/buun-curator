import { NextResponse } from "next/server";
import { discoverFeeds } from "@/lib/feed-discovery";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:feeds:discover");

// POST /api/feeds/discover - Discover feeds from a URL
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { url } = body;

    if (!url || typeof url !== "string") {
      return NextResponse.json({ error: "URL is required" }, { status: 400 });
    }

    const result = await discoverFeeds(url);

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "failed to discover feeds");
    return NextResponse.json(
      { error: "Failed to discover feeds" },
      { status: 500 },
    );
  }
}
