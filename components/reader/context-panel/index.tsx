"use client";

import { AnimatePresence, motion } from "framer-motion";
import * as React from "react";

import { cn } from "@/lib/utils";

import { ContextPanelHeader } from "./context-panel-header";
import { ContextView } from "./context-view";
import { DebugView } from "./debug-view";
import { useContextData } from "./hooks/use-context-data";
import { useLinkEnrichment } from "./hooks/use-link-enrichment";
import { usePanelResize } from "./hooks/use-panel-resize";
import { RelationshipsDialog } from "./relationships-dialog";
import { RepoDetailDialog } from "./repo-detail-dialog";
import type { GitHubRepo, ViewMode } from "./types";
interface ContextPanelProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  entryId?: string;
}

/**
 * Context Panel for debugging - slides up from bottom.
 *
 * Shows extracted context and enrichments for the current entry.
 */
export function ContextPanel({
  open,
  onOpenChange,
  entryId,
}: ContextPanelProps) {
  // View mode state
  const [viewMode, setViewMode] = React.useState<ViewMode>("context");

  // Selection state
  const [selectedRepos, setSelectedRepos] = React.useState<Set<string>>(
    new Set(),
  );
  const [selectedWebPages, setSelectedWebPages] = React.useState<Set<string>>(
    new Set(),
  );

  // Deleting state
  const [deletingWebPages, setDeletingWebPages] = React.useState<Set<string>>(
    new Set(),
  );

  // Dialog state
  const [detailRepo, setDetailRepo] = React.useState<GitHubRepo | null>(null);
  const [relationshipsDialogOpen, setRelationshipsDialogOpen] =
    React.useState(false);

  // Hooks
  const { data, loading, error, extracting, fetchContext, startExtraction } =
    useContextData({ entryId, open });
  const { height, isDragging, handleMouseDown } = usePanelResize();

  // Compute enriched URLs from context data
  const enrichedUrls = React.useMemo(() => {
    const urls = new Set<string>();
    for (const enrichment of data?.enrichments || []) {
      if (enrichment.type === "web_page" && enrichment.source) {
        urls.add(enrichment.source);
      }
    }
    return urls;
  }, [data?.enrichments]);

  const {
    addUrl: addLinkUrl,
    pendingUrls: pendingLinks,
    fetchingUrls: fetchingLinks,
    failedUrls: failedLinks,
  } = useLinkEnrichment({
    entryId,
    enrichedUrls,
    onWorkflowComplete: () => {
      // Refresh context data when workflow completes
      fetchContext();
    },
  });

  // Reset state when entry changes
  React.useEffect(() => {
    setSelectedRepos(new Set());
    setSelectedWebPages(new Set());
    setDeletingWebPages(new Set());
    setRelationshipsDialogOpen(false);
    setDetailRepo(null);
  }, [entryId]);

  // Toggle repo selection
  const toggleRepoSelection = React.useCallback((fullName: string) => {
    setSelectedRepos((prev) => {
      const next = new Set(prev);
      if (next.has(fullName)) {
        next.delete(fullName);
      } else {
        next.add(fullName);
      }
      return next;
    });
  }, []);

  // Toggle web page selection
  const toggleWebPageSelection = React.useCallback((url: string) => {
    setSelectedWebPages((prev) => {
      const next = new Set(prev);
      if (next.has(url)) {
        next.delete(url);
      } else {
        next.add(url);
      }
      return next;
    });
  }, []);

  // Delete web page enrichment
  const deleteWebPage = React.useCallback(
    async (url: string) => {
      if (!entryId || deletingWebPages.has(url)) return;

      // Mark as deleting
      setDeletingWebPages((prev) => new Set(prev).add(url));

      try {
        const response = await fetch(
          `/api/entries/${entryId}/delete-enrichment`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ type: "web_page", source: url }),
          },
        );

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || "Failed to delete enrichment");
        }

        // Refresh context data to update UI
        // The workflow will complete and trigger context refresh
        // For immediate feedback, we refetch after a short delay
        setTimeout(() => {
          fetchContext();
        }, 500);
      } catch (error) {
        console.error("Failed to delete web page enrichment:", error);
      } finally {
        // Remove from deleting set
        setDeletingWebPages((prev) => {
          const next = new Set(prev);
          next.delete(url);
          return next;
        });
      }
    },
    [entryId, deletingWebPages, fetchContext],
  );

  return (
    <>
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height, opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="flex shrink-0 flex-col overflow-hidden border-t bg-background"
          >
            {/* Resize Handle */}
            <div
              onMouseDown={handleMouseDown}
              className={cn(
                "relative flex h-px cursor-row-resize items-center justify-center bg-border",
                "after:absolute after:inset-x-0 after:top-1/2 after:h-1 after:-translate-y-1/2",
                "transition-colors hover:bg-primary/50",
                isDragging && "bg-primary",
              )}
            >
              <div className="absolute -top-1.5 z-10 flex h-3 w-4 items-center justify-center rounded-sm border bg-border" />
            </div>

            {/* Header */}
            <ContextPanelHeader
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              extracting={extracting}
              loading={loading}
              entryId={entryId}
              onStartExtraction={startExtraction}
              onRefresh={fetchContext}
              onClose={() => onOpenChange(false)}
            />

            {/* Content */}
            <div className="min-h-0 flex-1 overflow-auto">
              <div className="p-4">
                {viewMode === "context" ? (
                  <ContextView
                    entryId={entryId}
                    data={data}
                    loading={loading}
                    extracting={extracting}
                    error={error}
                    selectedRepos={selectedRepos}
                    selectedWebPages={selectedWebPages}
                    pendingLinks={pendingLinks}
                    fetchingLinks={fetchingLinks}
                    failedLinks={failedLinks}
                    deletingWebPages={deletingWebPages}
                    onToggleRepoSelection={toggleRepoSelection}
                    onToggleWebPageSelection={toggleWebPageSelection}
                    onEnrichLink={addLinkUrl}
                    onDeleteWebPage={deleteWebPage}
                    onShowRepoDetail={setDetailRepo}
                    onShowRelationships={() => setRelationshipsDialogOpen(true)}
                    onStartExtraction={startExtraction}
                  />
                ) : (
                  <DebugView
                    entryId={entryId}
                    data={data}
                    loading={loading}
                    extracting={extracting}
                    error={error}
                    onStartExtraction={startExtraction}
                  />
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Repository Detail Dialog */}
      <RepoDetailDialog
        repo={detailRepo}
        onOpenChange={(open) => !open && setDetailRepo(null)}
      />

      {/* Relationships Graph Dialog */}
      <RelationshipsDialog
        open={relationshipsDialogOpen}
        onOpenChange={setRelationshipsDialogOpen}
        relationships={data?.context?.relationships ?? []}
        entities={data?.context?.entities ?? []}
      />
    </>
  );
}
