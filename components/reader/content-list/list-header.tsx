"use client";

import * as React from "react";
import {
  Star,
  Circle,
  Inbox,
  ArrowDownWideNarrow,
  ArrowUpWideNarrow,
  Sparkles,
  RefreshCw,
  Search,
  ChevronRight,
  CheckCheck,
  CircleSmall,
} from "lucide-react";

import { cn } from "@/lib/utils";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FilterMode, SortMode } from "@/lib/types";
import type { SubscriptionInfo } from "@/hooks/use-selected-subscription-info";

interface ListHeaderProps {
  subscriptionInfo?: SubscriptionInfo | null;
  filterMode: FilterMode;
  onFilterModeChange?: (mode: FilterMode) => void;
  sortMode: SortMode;
  onSortModeChange?: (mode: SortMode) => void;
  searchQuery: string;
  onSearchQueryChange?: (query: string) => void;
  canRefetch: boolean;
  onRefetch?: () => void;
  isRefetching: boolean;
  onMarkAllAsRead?: () => void;
  isMarkingAllAsRead: boolean;
}

/**
 * Header component for the content list.
 *
 * Contains breadcrumb, filter/sort controls, and search input.
 */
export function ListHeader({
  subscriptionInfo,
  filterMode,
  onFilterModeChange,
  sortMode,
  onSortModeChange,
  searchQuery,
  onSearchQueryChange,
  canRefetch,
  onRefetch,
  isRefetching,
  onMarkAllAsRead,
  isMarkingAllAsRead,
}: ListHeaderProps) {
  const searchInputRef = React.useRef<HTMLInputElement>(null);
  const isSearchMode = filterMode === "search";

  // Focus search input when search mode is activated
  React.useEffect(() => {
    if (isSearchMode) {
      searchInputRef.current?.focus();
    }
  }, [isSearchMode]);

  return (
    <div className="shrink-0">
      {/* Row 1: Breadcrumb */}
      <div className="flex h-11 items-center gap-2 px-2">
        <div className="text-s flex min-w-0 flex-1 items-center gap-1 px-1 text-muted-foreground">
          {subscriptionInfo?.breadcrumb.map((item, index) => (
            <React.Fragment key={item.id}>
              {index > 0 && <ChevronRight className="size-3 shrink-0" />}
              <span
                className={cn(
                  "truncate",
                  index === subscriptionInfo.breadcrumb.length - 1 &&
                    "font-medium text-foreground",
                )}
              >
                {item.title}
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Row 2: Filter, Sort icons */}
      <div className="flex h-8 items-center gap-1 px-2.5 pb-1">
        {/* Filter toggles */}
        <ToggleGroup
          type="single"
          value={filterMode}
          onValueChange={(value) => {
            if (value) onFilterModeChange?.(value as FilterMode);
          }}
          size="sm"
          variant="outline"
        >
          <ToggleGroupItem
            value="unread"
            aria-label="Unread"
            title="Unread"
            className="size-6 p-0"
          >
            <CircleSmall className="size-3.5 fill-foreground" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="all"
            aria-label="All"
            title="All Entries"
            className="size-6 p-0"
          >
            <Inbox className="size-3.5" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="starred"
            aria-label="Starred"
            title="Starred"
            className="size-6 p-0"
          >
            <Star className="size-3.5" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="search"
            aria-label="Search"
            title="Search"
            className="size-6 p-0"
          >
            <Search className="size-3.5" />
          </ToggleGroupItem>
        </ToggleGroup>

        <div className="mx-1 h-4 w-px bg-border" />

        {/* Sort toggles */}
        <ToggleGroup
          type="single"
          value={sortMode}
          onValueChange={(value) => {
            if (value) onSortModeChange?.(value as SortMode);
          }}
          size="sm"
          variant="outline"
        >
          <ToggleGroupItem
            value="newest"
            aria-label="Newest first"
            title="Newest first"
            className="size-6 p-0"
          >
            <ArrowDownWideNarrow className="size-3.5" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="oldest"
            aria-label="Oldest first"
            title="Oldest first"
            className="size-6 p-0"
          >
            <ArrowUpWideNarrow className="size-3.5" />
          </ToggleGroupItem>
          <ToggleGroupItem
            value="recommended"
            aria-label="Recommended"
            title="Recommended"
            className="size-6 p-0"
          >
            <Sparkles className="size-3.5" />
          </ToggleGroupItem>
        </ToggleGroup>

        <div className="mx-1 h-4 w-px bg-border" />

        {/* Mark all as read button */}
        <Button
          variant="ghost"
          size="icon"
          className="size-6"
          onClick={onMarkAllAsRead}
          disabled={isMarkingAllAsRead || !onMarkAllAsRead}
          title="Mark all as read"
        >
          <CheckCheck
            className={cn("size-3.5", isMarkingAllAsRead && "animate-pulse")}
          />
        </Button>

        {/* Refetch button */}
        {canRefetch && (
          <Button
            variant="ghost"
            size="icon"
            className="size-6"
            onClick={onRefetch}
            disabled={isRefetching}
            title="Fetch new entries"
          >
            <RefreshCw
              className={cn("size-3.5", isRefetching && "animate-spin")}
            />
          </Button>
        )}
      </div>

      {/* Row 3: Search input (shown in search mode) */}
      {isSearchMode && (
        <div className="flex items-center gap-1 px-2 pb-2">
          <Input
            ref={searchInputRef}
            type="text"
            placeholder="Search entries..."
            value={searchQuery}
            onChange={(e) => onSearchQueryChange?.(e.target.value)}
            className="h-7 flex-1 text-xs"
            onKeyDown={(e) => {
              if (e.key === "Escape") {
                onFilterModeChange?.("unread");
              }
            }}
          />
        </div>
      )}
    </div>
  );
}
