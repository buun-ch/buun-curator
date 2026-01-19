import { NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import { startSingleFeedIngestionWorkflow } from "@/lib/temporal";

const log = createLogger("api:workflows:ingest-feed");

// POST /api/workflows/ingest-feed - Start single feed ingestion workflow
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const {
      feedId,
      feedName,
      feedUrl,
      etag,
      lastModified,
      fetchLimit,
      extractionRules,
      autoDistill,
      enableContentFetch,
      targetLanguage,
      enableThumbnail,
      domainFetchDelay,
    } = body;

    if (!feedId || typeof feedId !== "string") {
      return NextResponse.json(
        { error: "feedId is required" },
        { status: 400 },
      );
    }

    if (!feedName || typeof feedName !== "string") {
      return NextResponse.json(
        { error: "feedName is required" },
        { status: 400 },
      );
    }

    if (!feedUrl || typeof feedUrl !== "string") {
      return NextResponse.json(
        { error: "feedUrl is required" },
        { status: 400 },
      );
    }

    const handle = await startSingleFeedIngestionWorkflow({
      feedId,
      feedName,
      feedUrl,
      etag,
      lastModified,
      fetchLimit,
      extractionRules,
      autoDistill,
      enableContentFetch,
      targetLanguage,
      enableThumbnail,
      domainFetchDelay,
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
    });
  } catch (error) {
    log.error({ error }, "Failed to start single feed ingestion workflow");
    return NextResponse.json(
      { error: "Failed to start single feed ingestion workflow" },
      { status: 500 },
    );
  }
}
