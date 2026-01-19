/**
 * API endpoint for sending SSE events from internal services.
 *
 * Used by Temporal Worker to notify clients of workflow progress.
 * Authentication is handled by middleware via INTERNAL_API_TOKEN.
 *
 * Architecture:
 * - Worker sends full progress data directly via HTTP POST (type: "progress")
 * - This endpoint broadcasts to all connected SSE clients
 * - No Temporal Query is used (avoids blocking Worker during CPU-bound tasks)
 */

import { NextRequest, NextResponse } from "next/server";
import { broadcastEvent, type SSEEventType } from "../route";
import { createLogger } from "@/lib/logger";
import type { WorkflowProgress } from "@/lib/temporal";

const log = createLogger("api:events:send");

/** Debounce interval for progress events (ms). */
const PROGRESS_DEBOUNCE_MS = 100;

/** Pending progress data keyed by workflowId. */
const pendingProgress = new Map<
  string,
  { timer: NodeJS.Timeout; data: ProgressEventData }
>();

/** Request body schema for sending events. */
interface SendEventRequest {
  /** Event type */
  type: SSEEventType;
  /** Event payload */
  data: unknown;
}

/** Progress event data from Worker. */
interface ProgressEventData {
  workflowId: string;
  progress: WorkflowProgress;
}

/**
 * Broadcasts progress to all connected SSE clients.
 *
 * @param data - The progress event data from Worker
 */
function broadcastProgress(data: ProgressEventData): void {
  const { workflowId, progress } = data;
  broadcastEvent({ type: "update", data: { workflowId, progress } });
}

/**
 * Schedules a debounced progress broadcast for a workflow.
 *
 * If multiple updates arrive within the debounce period, only the last one
 * is broadcasted (with the latest progress data).
 *
 * @param data - The progress event data to schedule
 */
function scheduleProgressBroadcast(data: ProgressEventData): void {
  const { workflowId } = data;

  // Clear existing timer for this workflow
  const existing = pendingProgress.get(workflowId);
  if (existing) {
    clearTimeout(existing.timer);
  }

  // Schedule new broadcast after debounce period
  const timer = setTimeout(() => {
    const pending = pendingProgress.get(workflowId);
    if (pending) {
      pendingProgress.delete(workflowId);
      broadcastProgress(pending.data);
    }
  }, PROGRESS_DEBOUNCE_MS);

  // Store latest data (overwrites previous if debounced)
  pendingProgress.set(workflowId, { timer, data });
}

/**
 * POST /api/events/send - Broadcast an SSE event to all connected clients.
 *
 * For "progress" events, this endpoint debounces requests and broadcasts
 * the latest progress data directly (no Temporal Query).
 *
 * Requires Bearer token authentication via INTERNAL_API_TOKEN.
 */
export async function POST(request: NextRequest): Promise<NextResponse> {
  try {
    const body = (await request.json()) as SendEventRequest;

    // Validate request body
    if (!body.type || body.data === undefined) {
      return NextResponse.json(
        { error: "Missing required fields: type, data" },
        { status: 400 },
      );
    }

    // Validate event type
    const validTypes: SSEEventType[] = [
      "progress",
      "complete",
      "error",
      "keep-alive",
      "auth-expired",
    ];
    if (!validTypes.includes(body.type)) {
      return NextResponse.json(
        {
          error: `Invalid event type. Must be one of: ${validTypes.join(", ")}`,
        },
        { status: 400 },
      );
    }

    // For "progress" events, debounce and broadcast latest progress
    if (body.type === "progress") {
      const progressData = body.data as ProgressEventData;
      if (!progressData.workflowId || !progressData.progress) {
        return NextResponse.json(
          { error: "Missing workflowId or progress in progress event data" },
          { status: 400 },
        );
      }

      // Schedule debounced broadcast (returns immediately)
      scheduleProgressBroadcast(progressData);

      return NextResponse.json({ success: true });
    }

    // Broadcast other events as-is
    broadcastEvent({ type: body.type, data: body.data });

    log.debug({ type: body.type }, "event broadcasted");

    return NextResponse.json({ success: true });
  } catch (error) {
    log.error({ error }, "failed to send event");
    return NextResponse.json(
      { error: "Failed to send event" },
      { status: 500 },
    );
  }
}
