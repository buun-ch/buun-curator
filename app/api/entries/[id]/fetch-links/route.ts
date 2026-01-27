import { NextResponse } from "next/server";
import { z } from "zod";

import { createLogger } from "@/lib/logger";
import {
  getWorkflowStatus,
  startFetchEntryLinksWorkflow,
} from "@/lib/temporal";

const log = createLogger("api:entries:fetch-links");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/** Schema for POST request body. */
const fetchLinksSchema = z.object({
  urls: z.array(z.url()).min(1),
  timeout: z.number().min(10).max(300).optional(),
});

/**
 * POST /api/entries/[id]/fetch-links
 *
 * Starts the FetchEntryLinksWorkflow to fetch content from URLs
 * and save them as entry enrichments.
 */
export async function POST(request: Request, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    // Parse and validate request body
    const body = await request.json();
    const parseResult = fetchLinksSchema.safeParse(body);

    if (!parseResult.success) {
      return NextResponse.json(
        { error: "Invalid request body", details: parseResult.error.issues },
        { status: 400 },
      );
    }

    const { urls, timeout } = parseResult.data;

    const handle = await startFetchEntryLinksWorkflow({
      entryId,
      urls,
      timeout,
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      status: "started",
      urlCount: urls.length,
    });
  } catch (error) {
    log.error({ error }, "Failed to start fetch entry links workflow");
    return NextResponse.json(
      { error: "Failed to start fetch entry links workflow" },
      { status: 500 },
    );
  }
}

/**
 * GET /api/entries/[id]/fetch-links?workflowId=xxx
 *
 * Gets the status of a FetchEntryLinksWorkflow.
 */
export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const workflowId = url.searchParams.get("workflowId");

    if (!workflowId) {
      return NextResponse.json(
        { error: "workflowId is required" },
        { status: 400 },
      );
    }

    const status = await getWorkflowStatus(workflowId);

    return NextResponse.json(status);
  } catch (error) {
    log.error({ error }, "Failed to get workflow status");
    return NextResponse.json(
      { error: "Failed to get workflow status" },
      { status: 500 },
    );
  }
}
