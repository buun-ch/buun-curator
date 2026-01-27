import type { ViewMode } from "@/lib/types";

/** Subscription item in the sidebar hierarchy. */
export interface Subscription {
  id: string;
  title: string;
  type: "category" | "feed" | "special";
  count?: number;
  children?: Subscription[];
}

/** Props for the SubscriptionSidebar component. */
export interface SubscriptionSidebarProps {
  collapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  viewMode?: ViewMode;
  /** Callback when "Fetch new entries" workflow completes. */
  onFetchNewComplete?: () => Promise<void>;
  /** Callback after a subscription is selected (for mobile navigation). */
  onSubscriptionSelect?: (id: string) => void;
  /** Callback when settings is clicked (for mobile navigation). */
  onSettingsClick?: () => void;
}
