/**
 * Hook for managing labels and entry-label associations.
 *
 * @module hooks/use-labels
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { Label } from "@/lib/types";

/** Fetches all available labels. */
async function fetchLabels(): Promise<Label[]> {
  const response = await fetch("/api/labels");
  if (!response.ok) {
    throw new Error("Failed to fetch labels");
  }
  return response.json();
}

/** Creates a new label. */
async function createLabel(data: {
  name: string;
  color: string;
}): Promise<Label> {
  const response = await fetch("/api/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error("Failed to create label");
  }
  return response.json();
}

/** Deletes a label by ID. */
async function deleteLabel(id: string): Promise<void> {
  const response = await fetch(`/api/labels?id=${id}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete label");
  }
}

/** Adds a label to an entry. */
async function addLabelToEntry(
  entryId: string,
  labelId: string,
): Promise<Label> {
  const response = await fetch(`/api/entries/${entryId}/labels`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ labelId }),
  });
  if (!response.ok) {
    throw new Error("Failed to add label to entry");
  }
  return response.json();
}

/** Removes a label from an entry. */
async function removeLabelFromEntry(
  entryId: string,
  labelId: string,
): Promise<void> {
  const response = await fetch(
    `/api/entries/${entryId}/labels?labelId=${labelId}`,
    {
      method: "DELETE",
    },
  );
  if (!response.ok) {
    throw new Error("Failed to remove label from entry");
  }
}

/** Return type for useLabels hook. */
interface UseLabelsReturn {
  /** All available labels. */
  labels: Label[];
  /** Loading state for labels. */
  isLoading: boolean;
  /** Create a new label. */
  createLabel: (data: { name: string; color: string }) => Promise<Label>;
  /** Delete a label. */
  deleteLabel: (id: string) => Promise<void>;
  /** Check if mutation is in progress. */
  isMutating: boolean;
}

/**
 * Hook for managing available labels.
 *
 * Provides CRUD operations for the global label list.
 */
export function useLabels(): UseLabelsReturn {
  const queryClient = useQueryClient();

  const { data: labels = [], isLoading } = useQuery({
    queryKey: ["labels"],
    queryFn: fetchLabels,
    staleTime: 60000, // Cache for 1 minute
  });

  const createMutation = useMutation({
    mutationFn: createLabel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labels"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteLabel,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["labels"] });
    },
  });

  return {
    labels,
    isLoading,
    createLabel: createMutation.mutateAsync,
    deleteLabel: deleteMutation.mutateAsync,
    isMutating: createMutation.isPending || deleteMutation.isPending,
  };
}

/** Return type for useEntryLabels hook. */
interface UseEntryLabelsReturn {
  /** Add a label to the entry. */
  addLabel: (labelId: string) => Promise<Label>;
  /** Remove a label from the entry. */
  removeLabel: (labelId: string) => Promise<void>;
  /** Check if mutation is in progress. */
  isMutating: boolean;
}

/**
 * Hook for managing labels on a specific entry.
 *
 * @param entryId - The entry ID to manage labels for
 */
export function useEntryLabels(entryId: string): UseEntryLabelsReturn {
  const queryClient = useQueryClient();

  const addMutation = useMutation({
    mutationFn: (labelId: string) => addLabelToEntry(entryId, labelId),
    onSuccess: () => {
      // Invalidate entry query to refresh labels and keep status
      queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: (labelId: string) => removeLabelFromEntry(entryId, labelId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["entry", entryId] });
    },
  });

  return {
    addLabel: addMutation.mutateAsync,
    removeLabel: removeMutation.mutateAsync,
    isMutating: addMutation.isPending || removeMutation.isPending,
  };
}
