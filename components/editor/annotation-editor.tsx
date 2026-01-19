"use client";

import { useCallback } from "react";
import {
  Bold,
  Code,
  Heading1,
  Heading2,
  Heading3,
  Italic,
  List,
  ListOrdered,
  Strikethrough,
} from "lucide-react";
import type { Value } from "platejs";
import { Plate, usePlateEditor } from "platejs/react";
import { MarkdownPlugin } from "@platejs/markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";
import { Editor, EditorContainer } from "@/components/ui/plate/editor";
import { FixedToolbar } from "@/components/ui/plate/fixed-toolbar";
import { MarkToolbarButton } from "@/components/ui/plate/mark-toolbar-button";
import { ToolbarButton, ToolbarGroup } from "@/components/ui/plate/toolbar";
import { LinkToolbarButton } from "@/components/ui/plate/link-toolbar-button";
import { ListToolbarButton } from "@/components/ui/plate/list-classic-toolbar-button";
import { TableToolbarButton } from "@/components/ui/plate/table-toolbar-button";
import { BasicNodesKit } from "@/components/editor/plugins/basic-nodes-kit";
import { ListKit } from "@/components/editor/plugins/list-classic-kit";
import { LinkKit } from "@/components/editor/plugins/link-kit";
import { AutoformatKit } from "@/components/editor/plugins/autoformat-classic-kit";
import { TableKit } from "@/components/editor/plugins/table-kit";

/** Props for the AnnotationEditor component. */
interface AnnotationEditorProps {
  /** Initial Markdown content. */
  value: string;
  /** Callback when content changes (Markdown string). */
  onChange?: (value: string) => void;
  /** Whether the editor is read-only. */
  readOnly?: boolean;
  /** Placeholder text. */
  placeholder?: string;
  /** Additional CSS class for the editor container. */
  className?: string;
}

/** All plugins for the annotation editor with GFM support. */
const plugins = [
  ...BasicNodesKit,
  ...ListKit,
  ...LinkKit,
  ...TableKit,
  ...AutoformatKit,
  MarkdownPlugin.configure({
    options: {
      remarkPlugins: [remarkGfm],
    },
  }),
];

/** Default empty value for the editor. */
const emptyValue: Value = [{ type: "p", children: [{ text: "" }] }];

/**
 * Rich text editor for entry annotations using Plate.
 *
 * Supports Markdown input/output with formatting:
 * headings, bold, italic, code, strikethrough, links, and lists.
 */
export function AnnotationEditor({
  value,
  onChange,
  readOnly = false,
  placeholder = "Add your notes here...",
  className,
}: AnnotationEditorProps) {
  const editor = usePlateEditor({
    plugins,
    value: (editor) => {
      if (!value) {
        return emptyValue;
      }
      try {
        return editor.getApi(MarkdownPlugin).markdown.deserialize(value);
      } catch {
        return [{ type: "p", children: [{ text: value }] }];
      }
    },
  });

  // Handle change - serialize to markdown
  const handleChange = useCallback(
    ({ value: newValue }: { value: Value }) => {
      if (onChange && !readOnly) {
        try {
          const markdown = editor.getApi(MarkdownPlugin).markdown.serialize({ value: newValue });
          onChange(markdown);
        } catch {
          // Fallback: extract plain text
          const text = newValue
            .map((node) =>
              "children" in node
                ? (node.children as Array<{ text?: string }>)
                    .map((c) => c.text || "")
                    .join("")
                : ""
            )
            .join("\n");
          onChange(text);
        }
      }
    },
    [editor, onChange, readOnly]
  );

  return (
    <Plate editor={editor} onChange={handleChange}>
      <div
        className={cn(
          "rounded-md border border-input bg-background",
          "focus-within:ring-2 focus-within:ring-ring",
          className
        )}
      >
        {/* Toolbar */}
        {!readOnly && (
          <FixedToolbar className="rounded-t-md border-b p-1">
            {/* Headings */}
            <ToolbarGroup>
              <ToolbarButton
                onClick={() => editor.tf.h1.toggle()}
                tooltip="Heading 1"
              >
                <Heading1 />
              </ToolbarButton>
              <ToolbarButton
                onClick={() => editor.tf.h2.toggle()}
                tooltip="Heading 2"
              >
                <Heading2 />
              </ToolbarButton>
              <ToolbarButton
                onClick={() => editor.tf.h3.toggle()}
                tooltip="Heading 3"
              >
                <Heading3 />
              </ToolbarButton>
            </ToolbarGroup>

            {/* Marks */}
            <ToolbarGroup>
              <MarkToolbarButton nodeType="bold" tooltip="Bold (⌘+B)">
                <Bold />
              </MarkToolbarButton>
              <MarkToolbarButton nodeType="italic" tooltip="Italic (⌘+I)">
                <Italic />
              </MarkToolbarButton>
              <MarkToolbarButton nodeType="strikethrough" tooltip="Strikethrough">
                <Strikethrough />
              </MarkToolbarButton>
              <MarkToolbarButton nodeType="code" tooltip="Code (⌘+E)">
                <Code />
              </MarkToolbarButton>
            </ToolbarGroup>

            {/* Lists */}
            <ToolbarGroup>
              <ListToolbarButton nodeType="ul_classic">
                <List />
              </ListToolbarButton>
              <ListToolbarButton nodeType="ol_classic">
                <ListOrdered />
              </ListToolbarButton>
            </ToolbarGroup>

            {/* Link */}
            <ToolbarGroup>
              <LinkToolbarButton />
            </ToolbarGroup>

            {/* Table */}
            <ToolbarGroup>
              <TableToolbarButton />
            </ToolbarGroup>
          </FixedToolbar>
        )}

        {/* Editor */}
        <EditorContainer>
          <Editor
            readOnly={readOnly}
            placeholder={placeholder}
            variant="none"
            className={cn(
              "prose prose-sm prose-neutral dark:prose-invert max-w-none",
              "min-h-[100px] w-full px-3 py-2",
              "focus-visible:outline-none"
            )}
          />
        </EditorContainer>
      </div>
    </Plate>
  );
}
