import { NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import {
  getWorkflowStatus,
  startContextCollectionWorkflow,
} from "@/lib/temporal";

const log = createLogger("api:entries:context:collect");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/**
 * POST /api/entries/[id]/context/collect
 *
 * Starts the ContextCollectionWorkflow for the given entry.
 * This workflow extracts context and performs GitHub enrichment.
 */
export async function POST(_request: Request, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    const handle = await startContextCollectionWorkflow({
      entryIds: [entryId],
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      status: "started",
    });
  } catch (error) {
    log.error({ error }, "Failed to start context collection workflow");
    return NextResponse.json(
      { error: "Failed to start context collection workflow" },
      { status: 500 },
    );
  }
}

/**
 * GET /api/entries/[id]/context/collect?workflowId=xxx
 *
 * Gets the status of a ContextCollectionWorkflow.
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
