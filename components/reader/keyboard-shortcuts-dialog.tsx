/**
 * Dialog component for displaying keyboard shortcuts.
 *
 * @module components/reader/keyboard-shortcuts-dialog
 */

"use client";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  KEYBOARD_SHORTCUTS,
  type KeyboardShortcut,
} from "@/hooks/use-keyboard-shortcuts";

interface KeyboardShortcutsDialogProps {
  /** Whether the dialog is open. */
  open: boolean;
  /** Callback when open state changes. */
  onOpenChange: (open: boolean) => void;
}

/** Groups shortcuts by category. */
function groupByCategory(
  shortcuts: KeyboardShortcut[],
): Record<string, KeyboardShortcut[]> {
  return shortcuts.reduce(
    (acc, shortcut) => {
      if (!acc[shortcut.category]) {
        acc[shortcut.category] = [];
      }
      acc[shortcut.category].push(shortcut);
      return acc;
    },
    {} as Record<string, KeyboardShortcut[]>,
  );
}

/** Category display names. */
const CATEGORY_LABELS: Record<string, string> = {
  navigation: "Navigation",
  actions: "Actions",
  view: "View",
};

/**
 * Dialog that displays all available keyboard shortcuts.
 *
 * Shortcuts are grouped by category (navigation, actions, view).
 */
export function KeyboardShortcutsDialog({
  open,
  onOpenChange,
}: KeyboardShortcutsDialogProps) {
  const grouped = groupByCategory(KEYBOARD_SHORTCUTS);
  const categories = ["navigation", "actions", "view"];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Keyboard Shortcuts</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          {categories.map((category) => {
            const shortcuts = grouped[category];
            if (!shortcuts?.length) return null;
            return (
              <div key={category}>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">
                  {CATEGORY_LABELS[category] ?? category}
                </h3>
                <div className="space-y-1">
                  {shortcuts.map((shortcut) => (
                    <div
                      key={shortcut.key}
                      className="flex items-center justify-between py-1"
                    >
                      <span className="text-sm">{shortcut.description}</span>
                      <kbd className="rounded bg-muted px-2 py-0.5 font-mono text-xs">
                        {shortcut.key}
                      </kbd>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
