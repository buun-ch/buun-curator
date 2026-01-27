"use client";

import { Bug, Check, ChevronDown, ChevronRight, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import type { Entry } from "@/lib/types";

interface DebugPanelProps {
  entry: Entry;
}

/** Content field toggle component. */
function ContentToggle({
  label,
  content,
}: {
  label: string;
  content: string | undefined;
}) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (!content) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <ChevronRight className="size-3" />
        <span>{label}:</span>
        <span className="italic">empty</span>
      </div>
    );
  }

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <div className="flex items-center gap-2 text-xs">
        <CollapsibleTrigger className="flex items-center gap-2 hover:text-foreground">
          {open ? (
            <ChevronDown className="size-3" />
          ) : (
            <ChevronRight className="size-3" />
          )}
          <span>{label}:</span>
          <span className="text-muted-foreground">
            {content.length.toLocaleString()} chars
          </span>
        </CollapsibleTrigger>
        <button
          type="button"
          onClick={handleCopy}
          className="text-muted-foreground hover:text-foreground"
          title="Copy to clipboard"
        >
          {copied ? (
            <Check className="size-3 text-green-500" />
          ) : (
            <Copy className="size-3" />
          )}
        </button>
      </div>
      <CollapsibleContent>
        <pre className="mt-2 max-h-64 overflow-auto rounded bg-muted p-3 text-xs whitespace-pre-wrap">
          {content}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

/** Copyable value cell component. */
function CopyableValue({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <span className="inline-flex items-center gap-2">
      <span>{value}</span>
      <button
        type="button"
        onClick={handleCopy}
        className="text-muted-foreground hover:text-foreground"
        title="Copy to clipboard"
      >
        {copied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <Copy className="size-3" />
        )}
      </button>
    </span>
  );
}

/**
 * Debug panel component.
 *
 * Collapsible panel showing entry metadata and content fields.
 */
export function DebugPanel({ entry }: DebugPanelProps) {
  const metadata = entry.metadata as {
    distillTraceId?: string;
    summarizeTraceId?: string;
    mainContentStartLine?: number;
    mainContentEndLine?: number;
  } | null;

  // Table rows for metadata display
  const tableRows: Array<{ label: string; value: React.ReactNode }> = [
    { label: "id", value: <CopyableValue value={entry.id} /> },
    { label: "url", value: <CopyableValue value={entry.url} /> },
    { label: "feedId", value: <CopyableValue value={entry.feedId} /> },
    { label: "feedName", value: entry.feedName ?? "—" },
    { label: "author", value: entry.author ?? "—" },
    { label: "publishedAt", value: entry.publishedAt ?? "—" },
    { label: "createdAt", value: entry.createdAt },
    {
      label: "isRead",
      value: entry.isRead ? "true" : "false",
    },
    {
      label: "isStarred",
      value: entry.isStarred ? "true" : "false",
    },
    { label: "keep", value: entry.keep ? "true" : "false" },
    {
      label: "thumbnailUrl",
      value: entry.thumbnailUrl ? (
        <CopyableValue value={entry.thumbnailUrl} />
      ) : (
        "—"
      ),
    },
    {
      label: "distillTraceId",
      value: metadata?.distillTraceId ? (
        <CopyableValue value={metadata.distillTraceId} />
      ) : (
        "—"
      ),
    },
    {
      label: "mainContentStartLine",
      value: metadata?.mainContentStartLine ?? "-",
    },
    {
      label: "mainContentEndLine",
      value: metadata?.mainContentEndLine ?? "-",
    },
  ];

  return (
    <Collapsible className="mt-12 border-t pt-4">
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="flex w-full items-center justify-between text-muted-foreground hover:text-foreground"
        >
          <span className="flex items-center gap-2">
            <Bug className="size-4" />
            Debug
          </span>
          <ChevronDown className="size-4 transition-transform [[data-state=open]>&]:rotate-180" />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-4 space-y-6">
          {/* Similarity Score (for recommended sort) */}
          {entry.similarityScore !== undefined && (
            <div className="flex items-center gap-2 text-xs">
              <span className="font-medium text-muted-foreground">
                Cosine Distance:
              </span>
              <code className="rounded bg-muted px-2 py-0.5">
                {entry.similarityScore.toFixed(4)}
              </code>
              <span className="text-muted-foreground">
                (lower = more similar)
              </span>
            </div>
          )}

          {/* Metadata Table */}
          <table className="w-full text-xs">
            <tbody>
              {tableRows.map((row) => (
                <tr key={row.label} className="border-b border-muted">
                  <td className="py-1.5 pr-4 font-medium whitespace-nowrap text-muted-foreground">
                    {row.label}
                  </td>
                  <td className="py-1.5 font-mono break-all">{row.value}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Content Fields */}
          <div className="space-y-2">
            <ContentToggle label="feedContent" content={entry.feedContent} />
            <ContentToggle label="fullContent" content={entry.fullContent} />
            <ContentToggle
              label="filteredContent"
              content={entry.filteredContent}
            />
            <ContentToggle
              label="translatedContent"
              content={entry.translatedContent}
            />
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
