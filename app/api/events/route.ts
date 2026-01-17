/**
 * SSE endpoint for real-time notifications.
 *
 * Supports:
 * - Progress updates
 * - Task completion notifications
 * - Keep-alive messages
 * - Authentication validation
 */

import { auth } from "@/lib/auth";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:events");

// Store active connections for broadcasting
// Use globalThis to persist across hot reloads in development
const globalForSSE = globalThis as unknown as {
  sseConnections: Set<ReadableStreamDefaultController<Uint8Array>> | undefined;
};

const connections =
  globalForSSE.sseConnections ??
  (globalForSSE.sseConnections = new Set<ReadableStreamDefaultController<Uint8Array>>());

// Event types
export type SSEEventType =
  | "progress"
  | "complete"
  | "error"
  | "update"
  | "keep-alive"
  | "auth-expired";

export interface SSEEvent {
  type: SSEEventType;
  data: unknown;
}

/**
 * Broadcast an event to all connected clients.
 */
export function broadcastEvent(event: SSEEvent): void {
  const encoder = new TextEncoder();
  const message = `event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`;
  const encoded = encoder.encode(message);

  log.debug({ type: event.type, connections: connections.size }, `broadcasting event ${event.type}`);

  for (const controller of connections) {
    try {
      controller.enqueue(encoded);
    } catch {
      // Connection closed, will be cleaned up
      connections.delete(controller);
    }
  }
}

/**
 * Send an event to a specific controller.
 */
function sendEvent(
  controller: ReadableStreamDefaultController<Uint8Array>,
  event: SSEEvent
): void {
  const encoder = new TextEncoder();
  const message = `event: ${event.type}\ndata: ${JSON.stringify(event.data)}\n\n`;
  controller.enqueue(encoder.encode(message));
}

/**
 * Validate session from request headers.
 */
async function validateSession(
  headers: Headers
): Promise<{ valid: boolean; userId?: string }> {
  try {
    const session = await auth.api.getSession({
      headers,
      query: { disableCookieCache: true }, // Force DB check for accurate validation
    });
    return session ? { valid: true, userId: session.user.id } : { valid: false };
  } catch {
    return { valid: false };
  }
}

export async function GET(request: Request): Promise<Response> {
  // Check authentication on initial connection
  const sessionResult = await validateSession(request.headers);
  if (!sessionResult.valid) {
    return new Response("Unauthorized", { status: 401 });
  }

  // Store headers for session validation during keep-alive
  const requestHeaders = request.headers;

  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      // Add to active connections
      connections.add(controller);
      log.info({ userId: sessionResult.userId, connections: connections.size }, "client connected");

      // Send initial connection confirmation
      sendEvent(controller, {
        type: "keep-alive",
        data: { message: "connected", timestamp: Date.now() },
      });

      // Keep-alive interval with session validation (every 30 seconds)
      const keepAliveInterval = setInterval(async () => {
        try {
          // Validate session on each keep-alive
          const session = await validateSession(requestHeaders);

          if (!session.valid) {
            log.info({ userId: sessionResult.userId }, "session expired, closing connection");
            sendEvent(controller, {
              type: "auth-expired",
              data: { message: "Session expired", timestamp: Date.now() },
            });
            clearInterval(keepAliveInterval);
            connections.delete(controller);
            controller.close();
            return;
          }

          sendEvent(controller, {
            type: "keep-alive",
            data: { timestamp: Date.now() },
          });
        } catch {
          clearInterval(keepAliveInterval);
          connections.delete(controller);
        }
      }, 30000);

      // Cleanup on close
      return () => {
        clearInterval(keepAliveInterval);
        connections.delete(controller);
        log.info({ connections: connections.size }, "client disconnected");
      };
    },

    cancel() {
      // Stream cancelled by client
      log.debug({ connections: connections.size }, "stream cancelled");
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no", // Disable nginx buffering
    },
  });
}
