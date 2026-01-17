/**
 * SSE event type definitions.
 *
 * Shared types for server-sent events between worker and browser.
 *
 * @module lib/sse-events
 */

// =============================================================================
// Base Types
// =============================================================================

/** SSE event type identifiers. */
export type SSEEventType = "update" | "keep-alive" | "auth-expired";

// =============================================================================
// System Events
// =============================================================================

/** Keep-alive event payload. */
export interface KeepAlivePayload {
  /** Server timestamp. */
  timestamp: number;
  /** Optional message. */
  message?: string;
}

/** Auth expired event payload. */
export interface AuthExpiredPayload {
  /** Expiration message. */
  message: string;
  /** Server timestamp. */
  timestamp: number;
}

// =============================================================================
// Union Types
// =============================================================================

/** All possible SSE event payloads. */
export type SSEEventPayload = KeepAlivePayload | AuthExpiredPayload;

/** Typed SSE event structure. */
export type SSEEvent =
  | { type: "update"; data: { workflowId: string; progress?: unknown } }
  | { type: "keep-alive"; data: KeepAlivePayload }
  | { type: "auth-expired"; data: AuthExpiredPayload };
