"use client";

import { ChevronRight, Rss } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useSettingsStore } from "@/stores/settings-store";

import type { Subscription } from "./types";
import { SubscriptionItem } from "./subscription-item";

interface FeedsSectionProps {
  subscriptions: Subscription[];
  collapsed?: boolean;
  selectedId?: string;
  onSelect?: (id: string) => void;
}

/**
 * Feeds section wrapper component.
 *
 * Collapsible section containing all feed subscriptions.
 */
export function FeedsSection({
  subscriptions,
  collapsed,
  selectedId,
  onSelect,
}: FeedsSectionProps) {
  // Use store for collapse state (persisted to localStorage)
  const isOpen = useSettingsStore((state) => state.feedsSectionOpen);
  const setIsOpen = useSettingsStore((state) => state.setFeedsSectionOpen);

  // Calculate total unread count from "all" subscription or sum of all
  const totalCount = subscriptions.find((s) => s.id === "all")?.count ?? 0;

  // Filter out "all" from children since clicking "Feeds" now selects all
  const filteredSubscriptions = subscriptions.filter((s) => s.id !== "all");

  // "Feeds" itself is selected when "all" is selected
  const isFeedsSelected = selectedId === "all";

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div
        className={cn(
          "flex w-full items-center pl-1 text-sm font-medium select-none",
          isFeedsSelected && "bg-sidebar-accent",
          collapsed && "justify-center",
        )}
      >
        <CollapsibleTrigger asChild>
          <button
            className="flex items-center p-1.5 hover:bg-sidebar-accent"
            onClick={(e) => e.stopPropagation()}
          >
            <ChevronRight
              className={cn(
                "size-4 shrink-0 transition-transform",
                isOpen && "rotate-90",
                collapsed && "hidden",
              )}
            />
          </button>
        </CollapsibleTrigger>
        <button
          className={cn(
            "flex flex-1 items-center gap-1 py-1.5 pr-2 hover:bg-sidebar-accent",
            collapsed && "justify-center px-0",
          )}
          onClick={() => onSelect?.("all")}
        >
          <Rss className="size-4 text-muted-foreground" />
          {!collapsed && (
            <>
              <span className="flex-1 truncate text-left">Feeds</span>
              {totalCount > 0 && (
                <span className="text-xs font-normal text-muted-foreground">
                  {totalCount}
                </span>
              )}
            </>
          )}
        </button>
      </div>
      <CollapsibleContent>
        {filteredSubscriptions.map((subscription) => (
          <SubscriptionItem
            key={subscription.id}
            subscription={subscription}
            level={1}
            collapsed={collapsed}
            selectedId={selectedId}
            onSelect={onSelect}
          />
        ))}
      </CollapsibleContent>
    </Collapsible>
  );
}
