"use client";

import { FileQuestion, Loader2, Play, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";

import type { EntryContext } from "./types";

interface DebugViewProps {
  entryId?: string;
  data: EntryContext | null;
  loading: boolean;
  extracting: boolean;
  error: string | null;
  onStartExtraction: () => void;
}

/**
 * Debug view component showing raw context and enrichment data.
 *
 * Displays JSON representation of extracted data for debugging.
 */
export function DebugView({
  entryId,
  data,
  loading,
  extracting,
  error,
  onStartExtraction,
}: DebugViewProps) {
  if (!entryId) {
    return (
      <Empty className="py-8">
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <FileQuestion className="h-5 w-5" />
          </EmptyMedia>
          <EmptyTitle>No Entry Selected</EmptyTitle>
          <EmptyDescription>
            Select an entry to view debug information.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
  }

  if (loading || extracting) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        {extracting ? "Collecting context..." : "Loading context..."}
      </div>
    );
  }

  if (error) {
    return <div className="text-sm text-destructive">Error: {error}</div>;
  }

  if (!data) {
    return null;
  }

  return (
    <div className="space-y-6">
      {/* Entry Section */}
      <section>
        <h3 className="mb-2 text-sm font-semibold">Entry</h3>
        <div className="space-y-2 text-xs">
          <div className="flex gap-4">
            <span className="text-muted-foreground">Entry ID:</span>
            <pre>{entryId}</pre>
          </div>
        </div>
      </section>

      {/* Entry Context Section */}
      <section>
        <h3 className="mb-2 text-sm font-semibold">Entry Context</h3>
        <div className="space-y-2 text-xs">
          <div className="flex gap-4">
            <span className="text-muted-foreground">Saved At:</span>
            <span>
              {data.contextSavedAt
                ? new Date(data.contextSavedAt).toLocaleString()
                : "Not extracted"}
            </span>
          </div>
          <div className="flex gap-4">
            <span className="text-muted-foreground">Keep Context:</span>
            <span>{data.keepContext ? "Yes" : "No"}</span>
          </div>
          {data.context ? (
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted p-2 text-xs">
              {JSON.stringify(data.context, null, 2)}
            </pre>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">
                No context extracted yet
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={onStartExtraction}
                disabled={extracting}
              >
                <Play className="mr-1 h-3 w-3" />
                Extract
              </Button>
            </div>
          )}
        </div>
      </section>

      {/* Enrichments Section */}
      <section>
        <h3 className="mb-2 text-sm font-semibold">
          Enrichments ({data.enrichments.length})
        </h3>
        {data.enrichments.length > 0 ? (
          <div className="space-y-3">
            {data.enrichments.map((enrichment) => (
              <div key={enrichment.id} className="rounded border p-2">
                <div className="mb-1 flex items-center gap-2 text-xs">
                  <span className="rounded bg-primary/10 px-1.5 py-0.5 font-medium text-primary">
                    {enrichment.type}
                  </span>
                  {enrichment.source && (
                    <span className="text-muted-foreground">
                      {enrichment.source}
                    </span>
                  )}
                  <span className="text-muted-foreground">
                    {new Date(enrichment.createdAt).toLocaleString()}
                  </span>
                </div>
                {enrichment.metadata && (
                  <pre className="mt-1 max-h-24 overflow-auto rounded bg-muted p-1 text-xs">
                    {JSON.stringify(enrichment.metadata, null, 2)}
                  </pre>
                )}
                {enrichment.data && (
                  <pre className="mt-1 max-h-24 overflow-auto rounded bg-muted p-1 text-xs">
                    {JSON.stringify(enrichment.data, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-muted-foreground">No enrichments yet</div>
        )}
      </section>
    </div>
  );
}
