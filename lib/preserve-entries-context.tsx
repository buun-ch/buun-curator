"use client";

/**
 * React Context for preserving read entries in unread mode.
 *
 * Tracks entry IDs that were marked as read during the current session,
 * allowing them to remain visible in the list even after SSE-triggered
 * refetches. The preserved IDs are passed to the API to include them
 * in query results regardless of their read status.
 *
 * @module lib/preserve-entries-context
 */

import * as React from "react";
import { createLogger } from "@/lib/logger";

const log = createLogger("context:preserve-entries");

/** Context value for preserve entries. */
interface PreserveEntriesContextValue {
  /** Set of entry IDs to preserve in the list. */
  preserveIds: Set<string>;
  /** Add an entry ID to the preserve set. */
  addPreserveId: (id: string) => void;
  /** Clear all preserved IDs (called on filter/subscription change). */
  clearPreserveIds: () => void;
}

const PreserveEntriesContext =
  React.createContext<PreserveEntriesContextValue | null>(null);

/** Props for PreserveEntriesProvider. */
interface PreserveEntriesProviderProps {
  children: React.ReactNode;
}

/** Provider component for preserve entries context. */
export function PreserveEntriesProvider({
  children,
}: PreserveEntriesProviderProps) {
  const [preserveIds, setPreserveIds] = React.useState<Set<string>>(
    () => new Set()
  );

  const addPreserveId = React.useCallback((id: string) => {
    log.debug({ id }, "addPreserveId");
    setPreserveIds((prev) => {
      if (prev.has(id)) {
        log.debug({ id }, "addPreserveId: already exists");
        return prev;
      }
      const next = new Set(prev);
      next.add(id);
      log.debug({ count: next.size, ids: Array.from(next) }, "addPreserveId: updated");
      return next;
    });
  }, []);

  const clearPreserveIds = React.useCallback(() => {
    log.debug("clearPreserveIds called");
    setPreserveIds(new Set());
  }, []);

  const contextValue = React.useMemo(
    (): PreserveEntriesContextValue => ({
      preserveIds,
      addPreserveId,
      clearPreserveIds,
    }),
    [preserveIds, addPreserveId, clearPreserveIds]
  );

  return (
    <PreserveEntriesContext.Provider value={contextValue}>
      {children}
    </PreserveEntriesContext.Provider>
  );
}

/**
 * Hook to access preserve entries context.
 *
 * @returns Preserve entries context value
 * @throws Error if used outside PreserveEntriesProvider
 */
export function usePreserveEntries(): PreserveEntriesContextValue {
  const context = React.useContext(PreserveEntriesContext);
  if (!context) {
    throw new Error(
      "usePreserveEntries must be used within a PreserveEntriesProvider"
    );
  }
  return context;
}
