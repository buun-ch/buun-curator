import { NextRequest, NextResponse } from "next/server";

import { createLogger } from "@/lib/logger";
import {
  startTranslationWorkflow,
  getWorkflowStatus,
  type TranslationProvider,
} from "@/lib/temporal";

const log = createLogger("api:entries:translate");

interface RouteParams {
  params: Promise<{ id: string }>;
}

// POST /api/entries/[id]/translate - Start translation workflow for entry
export async function POST(request: NextRequest, { params }: RouteParams) {
  try {
    const { id: entryId } = await params;
    const provider = (process.env.TRANSLATION_PROVIDER ||
      "microsoft") as TranslationProvider;

    // Start the unified translation workflow with provider
    const handle = await startTranslationWorkflow({
      entryIds: [entryId],
      provider,
    });

    return NextResponse.json({
      workflowId: handle.workflowId,
      runId: handle.runId,
      status: "started",
      provider,
    });
  } catch (error) {
    log.error({ error }, "Failed to start translation workflow");
    return NextResponse.json(
      { error: "Failed to start translation workflow" },
      { status: 500 },
    );
  }
}

// GET /api/entries/[id]/translate?workflowId=xxx - Get translation status
export async function GET(request: NextRequest) {
  try {
    const workflowId = request.nextUrl.searchParams.get("workflowId");

    if (!workflowId) {
      return NextResponse.json(
        { error: "workflowId is required" },
        { status: 400 },
      );
    }

    const status = await getWorkflowStatus(workflowId);

    return NextResponse.json(status);
  } catch (error) {
    log.error({ error }, "Failed to get translation status");
    return NextResponse.json(
      { error: "Failed to get translation status" },
      { status: 500 },
    );
  }
}
