"use client";

import { useState, useCallback } from "react";
import dynamic from "next/dynamic";
import { Pencil, X, Check, Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import type { Entry } from "@/lib/types";
import { markdownComponents } from "./markdown-components";

// Dynamic import to avoid SSR issues with Plate
const AnnotationEditor = dynamic(
  () =>
    import("@/components/editor/annotation-editor").then(
      (mod) => mod.AnnotationEditor,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-[100px] items-center justify-center rounded-md border bg-muted/50">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    ),
  },
);

/** Props for the AnnotationSection component. */
interface AnnotationSectionProps {
  /** The entry to display/edit annotation for. */
  entry: Entry;
  /** Callback when annotation is updated. */
  onUpdate?: (annotation: string) => Promise<void>;
}

/**
 * Section for displaying and editing entry annotations.
 *
 * Shows the annotation as rendered Markdown in view mode,
 * and a Plate editor in edit mode.
 */
export function AnnotationSection({ entry, onUpdate }: AnnotationSectionProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(entry.annotation ?? "");
  const [isSaving, setIsSaving] = useState(false);

  const hasAnnotation = entry.annotation && entry.annotation.length > 0;

  const handleEdit = useCallback(() => {
    setEditValue(entry.annotation ?? "");
    setIsEditing(true);
  }, [entry.annotation]);

  const handleCancel = useCallback(() => {
    setEditValue(entry.annotation ?? "");
    setIsEditing(false);
  }, [entry.annotation]);

  const handleSave = useCallback(async () => {
    if (!onUpdate) return;

    setIsSaving(true);
    try {
      await onUpdate(editValue);
      setIsEditing(false);
    } finally {
      setIsSaving(false);
    }
  }, [editValue, onUpdate]);

  return (
    <section className="mt-8 border-t border-border/50 pt-6">
      {/* Header */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-medium text-muted-foreground">
          Annotation
        </h3>
        <div className="flex gap-2">
          {isEditing ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancel}
                disabled={isSaving}
              >
                <X className="mr-1 size-4" />
                Cancel
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={handleSave}
                disabled={isSaving}
              >
                {isSaving ? (
                  <Loader2 className="mr-1 size-4 animate-spin" />
                ) : (
                  <Check className="mr-1 size-4" />
                )}
                Save
              </Button>
            </>
          ) : (
            <Button variant="ghost" size="sm" onClick={handleEdit}>
              <Pencil className="mr-1 size-4" />
              Edit
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      {isEditing ? (
        <AnnotationEditor
          value={editValue}
          onChange={setEditValue}
          placeholder="Add your notes, thoughts, or additional content..."
        />
      ) : hasAnnotation ? (
        <div className="prose prose-sm max-w-none prose-neutral dark:prose-invert">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
          >
            {entry.annotation}
          </ReactMarkdown>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No annotation yet. Click Edit to add one.
        </p>
      )}
    </section>
  );
}
