import { NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import { startAllFeedsIngestionWorkflow } from "@/lib/temporal";

const log = createLogger("api:workflows:ingest");

// POST /api/workflows/ingest - Start all feeds ingestion workflow
// Config is read from environment variables at runtime
export async function POST() {
  try {
    const handle = await startAllFeedsIngestionWorkflow();

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
    });
  } catch (error) {
    log.error({ error }, "Failed to start ingestion workflow");
    return NextResponse.json(
      { error: "Failed to start ingestion workflow" },
      { status: 500 },
    );
  }
}
