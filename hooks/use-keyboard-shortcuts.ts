/**
 * Hook for managing global keyboard shortcuts.
 *
 * Provides vim-style navigation (j/k) for entry selection,
 * scroll controls, and common actions like starring entries.
 *
 * @module hooks/use-keyboard-shortcuts
 */

"use client";

import { useEffect, useRef, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";

/** Keyboard shortcut definition for help display. */
export interface KeyboardShortcut {
  /** Key combination (e.g., "j", "shift+j"). */
  key: string;
  /** Human-readable description. */
  description: string;
  /** Category for grouping in help display. */
  category: "navigation" | "actions" | "view";
}

/** All keyboard shortcuts with their descriptions. */
export const KEYBOARD_SHORTCUTS: KeyboardShortcut[] = [
  // Navigation
  { key: "j", description: "Next entry", category: "navigation" },
  { key: "k", description: "Previous entry", category: "navigation" },
  {
    key: "shift+j / space",
    description: "Scroll down",
    category: "navigation",
  },
  {
    key: "shift+k / shift+space",
    description: "Scroll up",
    category: "navigation",
  },
  { key: "gg", description: "Scroll to top", category: "navigation" },
  { key: "G", description: "Scroll to bottom", category: "navigation" },
  { key: "o", description: "Open entry in new tab", category: "navigation" },
  // Actions
  { key: "p", description: "Keep from auto-cleanup", category: "actions" },
  { key: "m", description: "Toggle read/unread", category: "actions" },
  { key: "s", description: "Toggle star", category: "actions" },
  { key: "l", description: "Focus label input", category: "actions" },
  // View
  { key: "shift+h", description: "Show keyboard shortcuts", category: "view" },
  // { key: "shift+w", description: "Toggle workflow panel", category: "view" },
];

/** Timeout for key sequences (ms). */
const SEQUENCE_TIMEOUT = 500;

/** Options for the useKeyboardShortcuts hook. */
interface UseKeyboardShortcutsOptions {
  /** Navigate to the next entry in the list. */
  onNextEntry?: () => void;
  /** Navigate to the previous entry in the list. */
  onPreviousEntry?: () => void;
  /** Scroll the content viewer down. */
  onScrollDown?: () => void;
  /** Scroll the content viewer up. */
  onScrollUp?: () => void;
  /** Scroll the content viewer to the top. */
  onScrollToTop?: () => void;
  /** Scroll the content viewer to the bottom. */
  onScrollToBottom?: () => void;
  /** Open the current entry in a new tab. */
  onOpenEntry?: () => void;
  /** Toggle star status of the current entry. */
  onToggleStar?: () => void;
  /** Toggle read/unread status of the current entry. */
  onToggleRead?: () => void;
  /** Toggle keep status of the current entry (preserve from auto-cleanup). */
  onToggleKeep?: () => void;
  /** Show keyboard shortcuts help. */
  onShowHelp?: () => void;
  /** Whether shortcuts are enabled (disable when modal/input is focused). */
  enabled?: boolean;
}

/**
 * Hook for registering global keyboard shortcuts.
 *
 * Registers vim-style navigation keys and common entry actions.
 * Shortcuts are automatically disabled when typing in form fields.
 *
 * @param options - Callback functions for each shortcut action
 */
export function useKeyboardShortcuts({
  onNextEntry,
  onPreviousEntry,
  onScrollDown,
  onScrollUp,
  onScrollToTop,
  onScrollToBottom,
  onOpenEntry,
  onToggleStar,
  onToggleRead,
  onToggleKeep,
  onShowHelp,
  enabled = true,
}: UseKeyboardShortcutsOptions): void {
  // preventDefault to avoid triggering focused button actions (j/k selecting buttons)
  const options = {
    enabled,
    preventDefault: true,
  };
  // Allow key repeat for continuous scrolling
  const scrollOptions = {
    enabled,
    keyup: false,
    keydown: true,
    preventDefault: true,
  };

  // Key sequence state for "gg" detection
  const [keySequence, setKeySequence] = useState("");
  const sequenceTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Clear sequence timeout on unmount
  useEffect(() => {
    return () => {
      if (sequenceTimeoutRef.current) {
        clearTimeout(sequenceTimeoutRef.current);
      }
    };
  }, []);

  // Navigation
  useHotkeys("j", () => onNextEntry?.(), options);
  useHotkeys("k", () => onPreviousEntry?.(), options);
  useHotkeys("shift+j", () => onScrollDown?.(), scrollOptions);
  useHotkeys("shift+k", () => onScrollUp?.(), scrollOptions);
  useHotkeys("space", () => onScrollDown?.(), scrollOptions);
  useHotkeys("shift+space", () => onScrollUp?.(), scrollOptions);
  useHotkeys("o", () => onOpenEntry?.(), options);

  // Sequence: "gg" for scroll to top
  useHotkeys(
    "g",
    () => {
      if (sequenceTimeoutRef.current) {
        clearTimeout(sequenceTimeoutRef.current);
      }
      if (keySequence === "g") {
        // gg detected
        onScrollToTop?.();
        setKeySequence("");
      } else {
        setKeySequence("g");
        sequenceTimeoutRef.current = setTimeout(
          () => setKeySequence(""),
          SEQUENCE_TIMEOUT,
        );
      }
    },
    options,
  );

  // "G" (shift+g) for scroll to bottom
  useHotkeys("shift+g", () => onScrollToBottom?.(), options);

  // Actions
  useHotkeys("s", () => onToggleStar?.(), options);
  useHotkeys("m", () => onToggleRead?.(), options);
  useHotkeys("p", () => onToggleKeep?.(), options);

  // View
  useHotkeys("shift+h", () => onShowHelp?.(), options);
}
