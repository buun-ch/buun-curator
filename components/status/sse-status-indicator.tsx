"use client";

import { RefreshCw } from "lucide-react";

import { useSSEContext } from "@/components/providers/sse-provider";
import { cn } from "@/lib/utils";

/**
 * Visual indicator for SSE connection status.
 *
 * Shows a small dot with color indicating status:
 * - Green: Connected
 * - Yellow: Connecting
 * - Red: Error
 * - Gray: Disconnected
 */
export function SSEStatusIndicator({ className }: { className?: string }) {
  const { status, isConnected, disconnect, connect } = useSSEContext();

  const statusColors = {
    connected: "bg-green-500",
    connecting: "bg-yellow-500 animate-pulse",
    error: "bg-red-500",
    disconnected: "bg-gray-400",
  };

  const statusLabels = {
    connected: "Connected",
    connecting: "Connecting...",
    error: "Connection error",
    disconnected: "Disconnected",
  };

  const handleReconnect = () => {
    disconnect();
    // Small delay to ensure clean disconnect
    setTimeout(() => {
      connect();
    }, 100);
  };

  return (
    <div
      className={cn("flex items-center gap-2", className)}
      data-testid="sse-status"
      data-status={status}
    >
      <div
        className={cn("size-2 rounded-full", statusColors[status])}
        title={statusLabels[status]}
      />
      <span className="px-1 text-sm text-foreground">
        {isConnected ? "Live" : statusLabels[status]}
      </span>
      <button
        onClick={handleReconnect}
        disabled={status === "connecting"}
        className={cn(
          "ml-auto rounded p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground",
          "disabled:cursor-not-allowed disabled:opacity-50",
          status === "connecting" && "animate-spin",
        )}
        title="Reconnect"
        data-testid="sse-reconnect"
      >
        <RefreshCw className="size-3" />
      </button>
    </div>
  );
}
