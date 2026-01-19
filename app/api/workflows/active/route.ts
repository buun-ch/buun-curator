/**
 * API endpoint for listing active workflows with progress.
 *
 * Used by SSE reconnection to restore UI state.
 */

import { NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import { listActiveWorkflows } from "@/lib/temporal";

const log = createLogger("api:workflows:active");

/**
 * GET /api/workflows/active - List all running workflows with progress.
 */
export async function GET(): Promise<NextResponse> {
  try {
    const workflows = await listActiveWorkflows();

    // Convert Date to ISO string for JSON serialization
    const serialized = workflows.map((wf) => ({
      ...wf,
      startTime: wf.startTime.toISOString(),
    }));

    return NextResponse.json(serialized);
  } catch (error) {
    log.error({ error }, "Failed to list active workflows");
    return NextResponse.json(
      { error: "Failed to list active workflows" },
      { status: 500 },
    );
  }
}
