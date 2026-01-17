/**
 * Hook for fetching and updating a single entry.
 *
 * Uses TanStack Query for caching and automatic refetching.
 * The entry data includes content fields and labels.
 *
 * @module hooks/use-entry
 */

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { type Entry, normalizeEntry } from "@/lib/types";

/**
 * Fetches a single entry by ID.
 *
 * @param entryId - The entry ID to fetch
 * @returns Full entry data with content and labels
 */
async function fetchEntry(entryId: string): Promise<Entry> {
  const response = await fetch(`/api/entries/${entryId}`);
  if (!response.ok) {
    throw new Error("Failed to fetch entry");
  }
  const entry = await response.json();
  return normalizeEntry(entry);
}

/** Options for the useEntry hook. */
interface UseEntryOptions {
  /** Whether to enable the query. */
  enabled?: boolean;
}

/** Return value from the useEntry hook. */
interface UseEntryReturn {
  /** The fetched entry data. */
  entry: Entry | undefined;
  /** True while loading. */
  isLoading: boolean;
  /** True if there was an error. */
  isError: boolean;
  /** Refetch the entry. */
  refetch: () => Promise<void>;
}

/**
 * Hook for fetching a single entry with full content.
 *
 * Uses the query key ["entry", entryId] for caching.
 * Invalidating this key will trigger a refetch.
 *
 * @param entryId - The entry ID to fetch (null/undefined disables the query)
 * @param options - Optional configuration
 * @returns Entry data and loading state
 */
export function useEntry(
  entryId: string | null | undefined,
  options?: UseEntryOptions
): UseEntryReturn {
  const { enabled = true } = options ?? {};

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["entry", entryId] as const,
    queryFn: () => fetchEntry(entryId!),
    enabled: enabled && !!entryId,
    staleTime: 30000, // Consider fresh for 30 seconds
  });

  return {
    entry: data,
    isLoading,
    isError,
    refetch: async () => {
      await refetch();
    },
  };
}

/** Fields that can be updated on an entry. */
export interface EntryUpdateData {
  isRead?: boolean;
  isStarred?: boolean;
  keep?: boolean;
}

/** Variables for the update entry mutation. */
interface UpdateEntryVariables {
  entryId: string;
  data: EntryUpdateData;
}

/**
 * Updates an entry via API.
 *
 * @param entryId - The entry ID to update
 * @param data - The fields to update
 */
async function updateEntryApi(
  entryId: string,
  data: EntryUpdateData
): Promise<void> {
  const response = await fetch(`/api/entries/${entryId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error("Failed to update entry");
  }
}

/** Context for optimistic updates rollback. */
interface UpdateEntryContext {
  previousEntry: Entry | undefined;
}

/** Options for the useUpdateEntry hook. */
export interface UseUpdateEntryOptions {
  /** Callback after successful update. */
  onSuccess?: (entryId: string, data: EntryUpdateData) => void;
  /** Callback on error. */
  onError?: (error: Error, variables: UpdateEntryVariables) => void;
}

/**
 * Hook for updating entry fields with optimistic updates.
 *
 * Updates the entry cache optimistically and rolls back on error.
 * Note: Callers should handle entries list updates separately via setEntries.
 *
 * @param options - Optional callbacks
 * @returns Mutation function and state
 */
export function useUpdateEntry(options?: UseUpdateEntryOptions) {
  const queryClient = useQueryClient();

  return useMutation<void, Error, UpdateEntryVariables, UpdateEntryContext>({
    mutationFn: ({ entryId, data }) => updateEntryApi(entryId, data),

    onMutate: async ({ entryId, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ["entry", entryId] });

      // Snapshot previous value
      const previousEntry = queryClient.getQueryData<Entry>(["entry", entryId]);

      // Optimistically update entry cache
      if (previousEntry) {
        queryClient.setQueryData<Entry>(["entry", entryId], {
          ...previousEntry,
          ...data,
        });
      }

      return { previousEntry };
    },

    onError: (error, { entryId }, context) => {
      // Rollback entry cache
      if (context?.previousEntry) {
        queryClient.setQueryData(["entry", entryId], context.previousEntry);
      }

      options?.onError?.(error, { entryId, data: {} });
    },

    onSuccess: (_, { entryId, data }) => {
      options?.onSuccess?.(entryId, data);
    },
  });
}

