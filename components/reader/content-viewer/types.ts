import type { Entry, LanguageMode } from "@/lib/types";

/** Props for the ContentViewer component. */
export interface ContentViewerProps {
  entry?: Entry | null;
  loading?: boolean;
  onToggleStar?: (entry: Entry) => void;
  onToggleKeep?: (entry: Entry) => void;
  onToggleRead?: (entry: Entry) => void;
  onRefresh?: (entry: Entry) => void | Promise<void>;
  refreshing?: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  hasPrevious?: boolean;
  hasNext?: boolean;
  /** Called when entry data needs to be refetched (e.g., after translation completes). */
  onEntryUpdated?: (entryId: string) => void;
  /** Current language mode (controlled from parent). */
  languageMode: LanguageMode;
  /** Callback when language mode changes. */
  onLanguageModeChange: (mode: LanguageMode) => void;
  /** Whether translation is in progress (from parent). */
  isTranslating?: boolean;
  /** Callback to trigger re-translation. */
  onRetranslate?: () => void;
  /** Whether context panel is open. */
  contextPanelOpen?: boolean;
  /** Callback when context panel open state changes. */
  onContextPanelOpenChange?: (open: boolean) => void;
  /** Callback when a related entry is selected for navigation. */
  onSelectEntry?: (entry: { id: string }) => void;
}

/** Methods exposed via ref for external control. */
export interface ContentViewerRef {
  /** Scroll the content area by the specified amount. */
  scrollBy: (amount: number) => void;
  /** Scroll the content area to the top. */
  scrollToTop: () => void;
  /** Scroll the content area to the bottom. */
  scrollToBottom: () => void;
}
