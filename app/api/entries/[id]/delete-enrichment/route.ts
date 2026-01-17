import { NextResponse } from "next/server";
import { z } from "zod";

import { createLogger } from "@/lib/logger";
import { startDeleteEnrichmentWorkflow } from "@/lib/temporal";

const log = createLogger("api:entries:delete-enrichment");

interface RouteParams {
  params: Promise<{ id: string }>;
}

/** Schema for POST request body. */
const deleteEnrichmentSchema = z.object({
  type: z.string().min(1),
  source: z.string().min(1),
});

/**
 * POST /api/entries/[id]/delete-enrichment
 *
 * Starts the DeleteEnrichmentWorkflow to delete an enrichment.
 */
export async function POST(request: Request, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;

    // Parse and validate request body
    const body = await request.json();
    const parseResult = deleteEnrichmentSchema.safeParse(body);

    if (!parseResult.success) {
      return NextResponse.json(
        { error: "Invalid request body", details: parseResult.error.issues },
        { status: 400 }
      );
    }

    const { type, source } = parseResult.data;

    const handle = await startDeleteEnrichmentWorkflow({
      entryId,
      enrichmentType: type,
      source,
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      status: "started",
    });
  } catch (error) {
    log.error({ error }, "Failed to start delete enrichment workflow");
    return NextResponse.json(
      { error: "Failed to start delete enrichment workflow" },
      { status: 500 }
    );
  }
}
