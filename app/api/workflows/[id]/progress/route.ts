/**
 * API endpoint for querying workflow progress via Temporal Query.
 */

import { NextRequest, NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import { queryWorkflowProgress } from "@/lib/temporal";

const log = createLogger("api:workflows:progress");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/**
 * GET /api/workflows/[id]/progress - Query workflow progress.
 */
export async function GET(_request: NextRequest, { params }: RouteParams) {
  try {
    const { id: workflowId } = await params;

    const progress = await queryWorkflowProgress(workflowId);

    if (!progress) {
      return NextResponse.json(
        { error: "Workflow not found or does not support progress query" },
        { status: 404 }
      );
    }

    return NextResponse.json(progress);
  } catch (error) {
    log.error({ error }, "Failed to query workflow progress");
    return NextResponse.json(
      { error: "Failed to query workflow progress" },
      { status: 500 }
    );
  }
}
