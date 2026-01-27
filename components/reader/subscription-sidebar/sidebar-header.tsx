"use client";

import {
  ChevronDown,
  Download,
  PanelLeft,
  PanelLeftClose,
  RefreshCw,
  RotateCw,
} from "lucide-react";
import Image from "next/image";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

interface SidebarHeaderProps {
  collapsed: boolean;
  isLoading: boolean;
  isScrolled: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  onRefresh: () => void;
  onFetchNew: () => void;
}

/**
 * Sidebar header component.
 *
 * Contains logo, refresh menu, and collapse toggle button.
 */
export function SidebarHeader({
  collapsed,
  isLoading,
  isScrolled,
  onCollapsedChange,
  onRefresh,
  onFetchNew,
}: SidebarHeaderProps) {
  return (
    <div
      className={cn(
        "flex h-11 shrink-0 items-center pr-1 pl-3 transition-[border-color] duration-200",
        isScrolled ? "border-b" : "border-b border-transparent",
        collapsed && "justify-center px-0",
      )}
    >
      {!collapsed && (
        <Image
          src="/icon.png"
          alt="Buun Curator"
          width={24}
          height={24}
          className="size-6 flex-1 object-contain"
          style={{ objectPosition: "left" }}
        />
      )}
      {!collapsed && (
        <DropdownMenu key="refresh-menu">
          <DropdownMenuTrigger key="refresh-dropdown" asChild>
            <Button
              key="subscription-refresh-button"
              variant="ghost"
              size="icon"
              className="size-8 gap-1 focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isLoading}
            >
              {isLoading ? (
                <RefreshCw className="size-4 animate-spin" />
              ) : (
                <>
                  <RefreshCw className="size-3.5" />
                  <ChevronDown className="size-2.5" />
                </>
              )}
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem onClick={onRefresh} disabled={isLoading}>
              <RotateCw className="mr-2 size-4" />
              Refresh
            </DropdownMenuItem>
            <DropdownMenuItem onClick={onFetchNew} disabled={isLoading}>
              <Download className="mr-2 size-4" />
              Fetch new entries
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="size-8"
        onClick={() => onCollapsedChange(!collapsed)}
      >
        {collapsed ? (
          <PanelLeft className="size-4" />
        ) : (
          <PanelLeftClose className="size-4" />
        )}
      </Button>
    </div>
  );
}
