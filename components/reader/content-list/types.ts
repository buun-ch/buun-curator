import type { SubscriptionInfo } from "@/hooks/use-selected-subscription-info";
import type { EntryListItem, FilterMode, SortMode } from "@/lib/types";

/** Props for the ContentList component. */
export interface ContentListProps {
  entries?: EntryListItem[];
  loading?: boolean;
  filterMode?: FilterMode;
  onFilterModeChange?: (mode: FilterMode) => void;
  sortMode?: SortMode;
  onSortModeChange?: (mode: SortMode) => void;
  hasMore?: boolean;
  loadingMore?: boolean;
  onLoadMore?: () => void;
  selectedId?: string;
  onSelect?: (entry: EntryListItem) => void;
  onToggleStar?: (entry: EntryListItem) => void;
  subscriptionInfo?: SubscriptionInfo | null;
  onRefetch?: () => void;
  isRefetching?: boolean;
  onMarkAllAsRead?: () => void;
  isMarkingAllAsRead?: boolean;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  /** Callback for back navigation (mobile). */
  onBack?: () => void;
}

/** Props for the EntryListItemComponent. */
export interface EntryListItemComponentProps {
  entry: EntryListItem;
  isSelected?: boolean;
  onSelect?: (entry: EntryListItem) => void;
  onToggleStar?: (entry: EntryListItem) => void;
}
