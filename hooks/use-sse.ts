"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import {
  fetchEventSource,
  EventStreamContentType,
} from "@microsoft/fetch-event-source";
import { createLogger } from "@/lib/logger";

const log = createLogger("sse:hook");

/** SSE connection status */
export type SSEStatus = "connecting" | "connected" | "disconnected" | "error";

/**
 * Keep-alive timeout threshold in milliseconds.
 * Server sends keep-alive every 30 seconds, so we use 45 seconds (30s + 15s buffer)
 * to detect stale connections after sleep/wake.
 */
const KEEPALIVE_TIMEOUT_MS = 45000;

/** SSE event handler */
export type SSEEventHandler<T = unknown> = (data: T) => void;

/** SSE hook options */
export interface UseSSEOptions {
  /** URL of the SSE endpoint */
  url?: string;
  /** Whether to automatically connect on mount */
  autoConnect?: boolean;
  /** Reconnect interval in milliseconds */
  reconnectInterval?: number;
  /** Maximum reconnect attempts (0 = infinite) */
  maxReconnectAttempts?: number;
  /** Called when workflow progress is updated. Progress is from Temporal Query. */
  onUpdate?: SSEEventHandler<{
    workflowId: string;
    progress?: {
      workflowId: string;
      workflowType: string;
      status: "running" | "completed" | "error";
      currentStep: string;
      message: string;
      startedAt: string;
      updatedAt: string;
      error?: string;
    };
  }>;
  /** Called when a keep-alive event is received */
  onKeepAlive?: SSEEventHandler<{ timestamp: number }>;
  /** Called when authentication expires */
  onAuthExpired?: SSEEventHandler<{ message: string; timestamp: number }>;
  /** Called when a workflow error event is received (Query failed) */
  onError?: SSEEventHandler<{ workflowId: string; error: string }>;
  /** Called when connection status changes */
  onStatusChange?: (status: SSEStatus) => void;
}

/**
 * Hook for SSE (Server-Sent Events) connection.
 *
 * Handles automatic reconnection and event dispatching.
 */
export function useSSE(options: UseSSEOptions = {}) {
  const {
    url = "/api/events",
    autoConnect = true,
    reconnectInterval = 3000,
    maxReconnectAttempts = 0,
    onUpdate,
    onKeepAlive,
    onAuthExpired,
    onError,
    onStatusChange,
  } = options;

  const [status, setStatus] = useState<SSEStatus>("disconnected");
  const [reconnectTrigger, setReconnectTrigger] = useState(0);
  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isConnectingRef = useRef(false);
  const lastKeepAliveRef = useRef<number>(-1);

  // Store callbacks in refs to avoid re-triggering useEffect
  const onUpdateRef = useRef(onUpdate);
  const onKeepAliveRef = useRef(onKeepAlive);
  const onAuthExpiredRef = useRef(onAuthExpired);
  const onErrorRef = useRef(onError);
  const onStatusChangeRef = useRef(onStatusChange);

  // Update refs when callbacks change
  useEffect(() => {
    onUpdateRef.current = onUpdate;
  }, [onUpdate]);

  useEffect(() => {
    onKeepAliveRef.current = onKeepAlive;
  }, [onKeepAlive]);

  useEffect(() => {
    onAuthExpiredRef.current = onAuthExpired;
  }, [onAuthExpired]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    onStatusChangeRef.current = onStatusChange;
  }, [onStatusChange]);

  // Update status and notify
  const updateStatus = useCallback((newStatus: SSEStatus) => {
    setStatus(newStatus);
    onStatusChangeRef.current?.(newStatus);
  }, []);

  // Disconnect from SSE
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }

    reconnectCountRef.current = 0;
    isConnectingRef.current = false;
    updateStatus("disconnected");
    log.info("disconnected");
  }, [updateStatus]);

  // Manual connect trigger
  const connect = useCallback(() => {
    updateStatus("connecting");
    setReconnectTrigger((t) => t + 1);
  }, [updateStatus]);

  // Actual connection logic in useEffect
  useEffect(() => {
    if (!autoConnect && reconnectTrigger === 0) {
      return;
    }

    // Prevent duplicate connections
    if (isConnectingRef.current) {
      return;
    }

    // Cleanup existing connection
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    isConnectingRef.current = true;

    // Set connecting status via microtask to avoid synchronous setState in effect
    queueMicrotask(() => {
      if (isConnectingRef.current) {
        updateStatus("connecting");
      }
    });

    fetchEventSource(url, {
      signal: abortController.signal,
      openWhenHidden: true, // Keep connection when tab is hidden

      async onopen(response) {
        if (
          response.ok &&
          response.headers.get("content-type")?.includes(EventStreamContentType)
        ) {
          log.info("connected");
          reconnectCountRef.current = 0;
          isConnectingRef.current = false;
          lastKeepAliveRef.current = Date.now();
          updateStatus("connected");
        } else if (response.status === 401) {
          // Authentication failed - notify and don't retry
          log.warn({ status: response.status }, "authentication failed");
          isConnectingRef.current = false;
          updateStatus("error");
          onAuthExpiredRef.current?.({
            message: "Session expired",
            timestamp: Date.now(),
          });
          // Don't throw - we don't want to trigger reconnect for auth failures
          abortControllerRef.current?.abort();
        } else {
          log.warn({ status: response.status }, "failed to connect");
          isConnectingRef.current = false;
          updateStatus("error");
          throw new Error(`Failed to connect: ${response.status}`);
        }
      },

      onmessage(event) {
        try {
          const data = JSON.parse(event.data);

          switch (event.event) {
            case "update":
              onUpdateRef.current?.(data);
              break;
            case "keep-alive":
              // Update last keep-alive timestamp for sleep/wake detection
              lastKeepAliveRef.current = Date.now();
              onKeepAliveRef.current?.(data);
              break;
            case "auth-expired":
              onAuthExpiredRef.current?.(data);
              break;
            case "error":
              onErrorRef.current?.(data);
              break;
            default:
              log.warn({ event: event.event, data }, "unknown event");
          }
        } catch (e) {
          log.error({ error: e }, "failed to parse event");
        }
      },

      onclose() {
        log.info("connection closed");
        isConnectingRef.current = false;
        updateStatus("disconnected");

        // Attempt reconnect
        if (
          maxReconnectAttempts === 0 ||
          reconnectCountRef.current < maxReconnectAttempts
        ) {
          reconnectCountRef.current++;
          log.info(
            { interval: reconnectInterval, attempt: reconnectCountRef.current },
            "reconnecting",
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectTrigger((t) => t + 1);
          }, reconnectInterval);
        }
      },

      onerror(err) {
        log.error({ error: err }, "error");
        isConnectingRef.current = false;
        updateStatus("error");

        // Don't retry on fatal errors
        if (err instanceof Error && err.name === "AbortError") {
          return; // Don't throw, connection was intentionally aborted
        }

        // Schedule reconnect (same logic as onclose)
        if (
          maxReconnectAttempts === 0 ||
          reconnectCountRef.current < maxReconnectAttempts
        ) {
          reconnectCountRef.current++;
          log.info(
            { interval: reconnectInterval, attempt: reconnectCountRef.current },
            "scheduling reconnect after error",
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            setReconnectTrigger((t) => t + 1);
          }, reconnectInterval);
        }

        // Throw to signal error to fetchEventSource
        throw err;
      },
    });

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      isConnectingRef.current = false;
    };
  }, [
    url,
    autoConnect,
    reconnectTrigger,
    reconnectInterval,
    maxReconnectAttempts,
    updateStatus,
  ]);

  // Force reconnect when keep-alive timeout is detected
  const forceReconnect = useCallback((reason: string) => {
    log.info(
      {
        elapsed: Date.now() - lastKeepAliveRef.current,
        threshold: KEEPALIVE_TIMEOUT_MS,
      },
      `${reason}, reconnecting`,
    );
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    isConnectingRef.current = false;
    reconnectCountRef.current = 0;
    lastKeepAliveRef.current = Date.now();
    setReconnectTrigger((t) => t + 1);
  }, []);

  // Periodic keep-alive timeout check (detects stale connections while tab is visible)
  useEffect(() => {
    if (status !== "connected") {
      return;
    }

    const checkKeepAlive = () => {
      // Skip if not yet initialized (first keep-alive not received)
      if (lastKeepAliveRef.current < 0) {
        return;
      }
      const elapsed = Date.now() - lastKeepAliveRef.current;
      if (elapsed > KEEPALIVE_TIMEOUT_MS) {
        forceReconnect("keep-alive timeout detected");
      }
    };

    // Check every 10 seconds
    const intervalId = setInterval(checkKeepAlive, 10000);

    return () => {
      clearInterval(intervalId);
    };
  }, [status, forceReconnect]);

  // Detect sleep/wake via visibility change and check keep-alive timeout
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible" && status === "connected") {
        // Skip if not yet initialized
        if (lastKeepAliveRef.current < 0) {
          return;
        }
        const elapsed = Date.now() - lastKeepAliveRef.current;
        if (elapsed > KEEPALIVE_TIMEOUT_MS) {
          forceReconnect("keep-alive timeout after wake");
        }
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [status, forceReconnect]);

  return {
    status,
    connect,
    disconnect,
    isConnected: status === "connected",
    isConnecting: status === "connecting",
  };
}
