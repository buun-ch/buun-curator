"use client";

import { useRef, useCallback, useMemo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useHotkeys } from "react-hotkeys-hook";
import type Tagify from "@yaireo/tagify";

import { useLabels, useEntryLabels } from "@/hooks/use-labels";
import type { Label } from "@/lib/types";

import "./entry-labels.css";

// Dynamic import to avoid SSR issues with Tagify
const Tags = dynamic(() => import("@yaireo/tagify/dist/react.tagify"), {
  ssr: false,
  loading: () => <div className="h-6" />,
});

interface EntryLabelsProps {
  entryId: string;
  labels: Label[];
  onLabelsChange?: (labels: Label[]) => void;
}

/** Default colors for new labels. */
const DEFAULT_COLORS = [
  "#fad2e1", // red
  "#fff1e6", // orange
  "#f0efeb", // yellow
  "#e2ece9", // green
  "#bee1e6", // cyan
  "#dfe7fd", // blue
  "#cddafd", // violet
  "#fde2e4", // pink
];
// const DEFAULT_COLORS = [
//   "#ef4444", // red
//   "#f97316", // orange
//   "#eab308", // yellow
//   "#22c55e", // green
//   "#06b6d4", // cyan
//   "#3b82f6", // blue
//   "#8b5cf6", // violet
//   "#ec4899", // pink
// ];

/**
 * Gets a deterministic color based on label name.
 *
 * Uses a simple hash function to ensure the same label name always
 * gets the same color, avoiding color instability during re-renders.
 */
function getColorForLabel(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    const char = name.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return DEFAULT_COLORS[Math.abs(hash) % DEFAULT_COLORS.length];
}

/**
 * Entry labels component using Tagify.
 *
 * Displays labels as colored tags with autocomplete for existing labels.
 */
export function EntryLabels({
  entryId,
  labels: initialLabels,
  onLabelsChange,
}: EntryLabelsProps) {
  const tagifyRef = useRef<Tagify>(null!);

  // Local state for optimistic updates
  const [localLabels, setLocalLabels] = useState<Label[]>(initialLabels);

  // Ref to always have access to the latest localLabels (avoids stale closure issues)
  const localLabelsRef = useRef<Label[]>(localLabels);
  localLabelsRef.current = localLabels;

  // Sync with props when they change from outside (compare by IDs to avoid infinite loops)
  const initialLabelIds = useMemo(
    () =>
      initialLabels
        .map((l) => l.id)
        .sort()
        .join(","),
    [initialLabels],
  );
  useEffect(() => {
    setLocalLabels(initialLabels);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialLabelIds]);

  const { labels: allLabels, createLabel } = useLabels();
  const { addLabel, removeLabel } = useEntryLabels(entryId);

  // Build whitelist for autocomplete (memoized)
  const whitelist = useMemo(
    () =>
      allLabels.map((label) => ({
        value: label.name,
        id: label.id,
        color: label.color,
      })),
    [allLabels],
  );

  // Tagify settings (whitelist is passed as separate prop for dynamic updates)
  const settings: Tagify.TagifySettings = {
    dropdown: {
      enabled: 1, // Show suggestions after 1 character
      maxItems: 10,
      closeOnSelect: true,
      highlightFirst: true,
      fuzzySearch: true,
    },
    enforceWhitelist: false, // Allow new labels
    duplicates: false,
    editTags: false,
    // Transform tag to show color
    transformTag: (tagData) => {
      // If it's an existing label, use its color
      const existingLabel = allLabels.find((l) => l.name === tagData.value);
      if (existingLabel) {
        tagData.style = `--tag-bg: ${existingLabel.color}`;
        tagData.id = existingLabel.id;
        tagData.color = existingLabel.color;
      } else {
        // New label - assign deterministic color based on name
        const color = getColorForLabel(tagData.value);
        tagData.style = `--tag-bg: ${color}`;
        tagData.color = color;
      }
    },
    templates: {
      tag: function (tagData) {
        const bgColor = tagData.color || "#6b7280";
        return `
          <tag title="${tagData.value}"
               contenteditable='false'
               spellcheck='false'
               tabIndex="-1"
               class="tagify__tag"
               style="--tag-bg: ${bgColor}">
            <x title='' class='tagify__tag__removeBtn' role='button' aria-label='remove tag'></x>
            <div>
              <span class='tagify__tag-text'>${tagData.value}</span>
            </div>
          </tag>
        `;
      },
      dropdownItem: function (tagData) {
        const bgColor = tagData.color || "#6b7280";
        return `
          <div class='tagify__dropdown__item' tabindex="0" role="option">
            <span class="tagify__dropdown__item__color" style="background: ${bgColor}"></span>
            ${tagData.value}
          </div>
        `;
      },
    },
  };

  // Handle tag addition (for manual entry with Enter key)
  const handleAdd = useCallback(
    async (e: CustomEvent<Tagify.AddEventData>) => {
      const tagData = e.detail.data;
      if (!tagData) return;

      // Use ref to get latest localLabels (avoids stale closure)
      const currentLabels = localLabelsRef.current;

      // Skip if this label is already in localLabels (prevents infinite loop from value sync)
      if (currentLabels.some((l) => l.name === tagData.value)) {
        return;
      }

      try {
        // Check if it's an existing label in the global list
        const existingLabel = allLabels.find((l) => l.name === tagData.value);

        if (existingLabel) {
          // Optimistic update
          const newLabels = [...currentLabels, existingLabel];
          setLocalLabels(newLabels);
          onLabelsChange?.(newLabels);
          // Add existing label to entry
          await addLabel(existingLabel.id);
        } else {
          // Create new label first, then add to entry
          const color =
            (tagData as { color?: string }).color ||
            getColorForLabel(tagData.value);
          const newLabel = await createLabel({ name: tagData.value, color });
          // Optimistic update
          const newLabels = [...localLabelsRef.current, newLabel];
          setLocalLabels(newLabels);
          onLabelsChange?.(newLabels);
          await addLabel(newLabel.id);
        }
      } catch (error) {
        console.error("Failed to add label:", error);
        // Revert optimistic update on failure
        setLocalLabels(currentLabels);
        // Remove the tag if the operation failed
        tagifyRef.current?.removeTags(tagData.value);
      }
    },
    [allLabels, addLabel, createLabel, onLabelsChange],
  );

  // Handle tag removal
  const handleRemove = useCallback(
    async (e: CustomEvent<Tagify.RemoveEventData>) => {
      const tagData = e.detail.data;
      if (!tagData) return;

      // Use ref to get latest localLabels (avoids stale closure)
      const currentLabels = localLabelsRef.current;

      // Find the label by name (also serves as skip if already removed)
      const label = currentLabels.find((l) => l.name === tagData.value);
      if (!label) return;

      // Optimistic update - remove immediately from local state
      const newLabels = currentLabels.filter((l) => l.id !== label.id);
      setLocalLabels(newLabels);
      onLabelsChange?.(newLabels);

      try {
        await removeLabel(label.id);
      } catch (error) {
        console.error("Failed to remove label:", error);
        // Revert optimistic update on failure - use functional update to get latest state
        setLocalLabels((prev) => {
          // Only revert if the label isn't already there
          if (!prev.some((l) => l.id === label.id)) {
            return [...prev, label];
          }
          return prev;
        });
        // Re-add the tag since removal failed
        tagifyRef.current?.addTags([
          {
            value: label.name,
            id: label.id,
            color: label.color,
          },
        ]);
      }
    },
    [removeLabel, onLabelsChange],
  );

  // Convert current labels to tagify format (memoized to prevent re-renders)
  const value = useMemo(
    () =>
      localLabels.map((label) => ({
        value: label.name,
        id: label.id,
        color: label.color,
        style: `--tag-bg: ${label.color}`,
      })),
    [localLabels],
  );

  // Handle dropdown selection - Tagify React wrapper doesn't automatically add tags from dropdown
  const handleDropdownSelect = useCallback(
    async (e: CustomEvent<Tagify.DropDownSelectEventData>) => {
      const elm = e.detail.elm;
      // With custom templates, __tagifyTagData may not be set
      // Extract label name from element text content instead
      const labelName = elm.textContent?.trim();
      if (!labelName) return;

      const currentLabels = localLabelsRef.current;

      // Skip if already in localLabels
      if (currentLabels.some((l) => l.name === labelName)) {
        return;
      }

      try {
        const existingLabel = allLabels.find((l) => l.name === labelName);

        if (existingLabel) {
          // Optimistic update
          const newLabels = [...currentLabels, existingLabel];
          setLocalLabels(newLabels);
          onLabelsChange?.(newLabels);
          // Add existing label to entry
          await addLabel(existingLabel.id);
        } else {
          // Create new label (shouldn't happen for dropdown selection, but handle anyway)
          const color = getColorForLabel(labelName);
          const newLabel = await createLabel({ name: labelName, color });
          const newLabels = [...localLabelsRef.current, newLabel];
          setLocalLabels(newLabels);
          onLabelsChange?.(newLabels);
          await addLabel(newLabel.id);
        }
      } catch (error) {
        console.error("Failed to add label from dropdown:", error);
      }
    },
    [allLabels, addLabel, createLabel, onLabelsChange],
  );

  // Keyboard shortcut: 'l' to focus label input
  useHotkeys(
    "l",
    () => {
      tagifyRef.current?.DOM.input.focus();
    },
    { preventDefault: true },
  );

  return (
    <div className="entry-labels">
      <Tags
        tagifyRef={tagifyRef}
        settings={settings}
        whitelist={whitelist}
        value={value}
        onAdd={handleAdd}
        onRemove={handleRemove}
        onDropdownSelect={handleDropdownSelect}
        placeholder="no labels"
      />
    </div>
  );
}
