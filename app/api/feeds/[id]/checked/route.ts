import { NextResponse } from "next/server";

import { updateFeedChecked } from "@/lib/api/feeds";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:feeds:checked");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// POST /api/feeds/[id]/checked - Update feed's checkedAt and cache headers
export async function POST(request: Request, { params }: RouteParams) {
  try {
    const { id: feedId } = await params;
    const body = await request.json();
    const { etag, lastModified } = body;

    const result = await updateFeedChecked(feedId, { etag, lastModified });

    if ("error" in result) {
      return NextResponse.json({ error: result.error }, { status: 404 });
    }

    return NextResponse.json(result);
  } catch (error) {
    log.error({ error }, "Failed to update feed checked");
    return NextResponse.json(
      { error: "Failed to update feed checked" },
      { status: 500 }
    );
  }
}
