import { NextRequest, NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import { getWorkflowStatus } from "@/lib/temporal";

const log = createLogger("api:workflows:status");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// GET /api/workflows/[id]/status - Get workflow status
export async function GET(_request: NextRequest, { params }: RouteParams) {
  try {
    const { id: workflowId } = await params;

    const status = await getWorkflowStatus(workflowId);

    return NextResponse.json(status);
  } catch (error) {
    log.error({ error }, "failed to get workflow status");
    return NextResponse.json(
      { error: "Failed to get workflow status" },
      { status: 500 },
    );
  }
}
