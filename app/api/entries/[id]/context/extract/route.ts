import { NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import {
  startExtractEntryContextWorkflow,
  getWorkflowStatus,
} from "@/lib/temporal";

const log = createLogger("api:entries:context:extract");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/**
 * POST /api/entries/[id]/context/extract
 *
 * Starts the ExtractEntryContextWorkflow for the given entry.
 */
export async function POST(_request: Request, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const handle = await startExtractEntryContextWorkflow({ entryId });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      status: "started",
    });
  } catch (error) {
    log.error({ error }, "Failed to start context extraction workflow");
    return NextResponse.json(
      { error: "Failed to start context extraction workflow" },
      { status: 500 }
    );
  }
}

/**
 * GET /api/entries/[id]/context/extract?workflowId=xxx
 *
 * Gets the status of an ExtractEntryContextWorkflow.
 */
export async function GET(request: Request) {
  try {
    const url = new URL(request.url);
    const workflowId = url.searchParams.get("workflowId");

    if (!workflowId) {
      return NextResponse.json(
        { error: "workflowId is required" },
        { status: 400 }
      );
    }

    const status = await getWorkflowStatus(workflowId);

    return NextResponse.json(status);
  } catch (error) {
    log.error({ error }, "Failed to get workflow status");
    return NextResponse.json(
      { error: "Failed to get workflow status" },
      { status: 500 }
    );
  }
}
