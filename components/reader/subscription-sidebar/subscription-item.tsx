"use client";

import { ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useSettingsStore } from "@/stores/settings-store";

import type { Subscription } from "./types";
import { getSubscriptionIcon } from "./icons";

interface SubscriptionItemProps {
  subscription: Subscription;
  level?: number;
  collapsed?: boolean;
  selectedId?: string;
  onSelect?: (id: string) => void;
}

/**
 * Recursive subscription item component.
 *
 * Renders a single subscription with optional children (for categories).
 */
export function SubscriptionItem({
  subscription,
  level = 0,
  collapsed,
  selectedId,
  onSelect,
}: SubscriptionItemProps) {
  // Use store for category collapse state (persisted to localStorage)
  const categoryCollapseState = useSettingsStore(
    (state) => state.categoryCollapseState,
  );
  const setCategoryOpen = useSettingsStore((state) => state.setCategoryOpen);
  // Default to open (true) if not in state
  const isOpen = categoryCollapseState[subscription.id] ?? true;
  const setIsOpen = (open: boolean) => setCategoryOpen(subscription.id, open);

  const hasChildren = subscription.children && subscription.children.length > 0;
  const isCategory = subscription.type === "category";
  const isSelected = selectedId === subscription.id;
  const icon = getSubscriptionIcon(subscription);

  // Calculate left padding based on level
  const paddingLeft = collapsed ? undefined : `${level * 12 + 8}px`;

  // Categories always show collapsible UI (even when empty) so they look like categories
  if (isCategory || hasChildren) {
    return (
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <div
          className={cn(
            "flex w-full items-center text-sm select-none",
            isSelected && "bg-sidebar-accent",
            collapsed && "justify-center",
          )}
          style={{ paddingLeft }}
        >
          <CollapsibleTrigger asChild>
            <button
              className="flex items-center px-1 py-1.5 hover:bg-sidebar-accent"
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
              "flex min-w-0 flex-1 items-center gap-0.5 py-1.5 pr-2 hover:bg-sidebar-accent",
              collapsed && "justify-center px-0",
            )}
            onClick={() => onSelect?.(subscription.id)}
          >
            {icon}
            {!collapsed && (
              <>
                <span className="flex-1 truncate pl-1 text-left">
                  {subscription.title}
                </span>
                {subscription.count != null && subscription.count > 0 && (
                  <span className="text-xs text-sidebar-foreground">
                    {subscription.count}
                  </span>
                )}
              </>
            )}
          </button>
        </div>
        <CollapsibleContent>
          {subscription.children?.map((child) => (
            <SubscriptionItem
              key={child.id}
              subscription={child}
              level={level + 1}
              collapsed={collapsed}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </CollapsibleContent>
      </Collapsible>
    );
  }

  return (
    <button
      onClick={() => onSelect?.(subscription.id)}
      className={cn(
        "flex w-full items-center gap-0.5 px-2 py-1.5 text-sm select-none hover:bg-sidebar-accent",
        isSelected && "bg-sidebar-accent",
        collapsed && "justify-center px-0",
      )}
      style={{ paddingLeft }}
    >
      {icon}
      {!collapsed && (
        <>
          <span className="flex-1 truncate pl-1 text-left">
            {subscription.title}
          </span>
          {subscription.count != null && subscription.count > 0 && (
            <span className="text-xs text-sidebar-foreground">
              {subscription.count}
            </span>
          )}
        </>
      )}
    </button>
  );
}
