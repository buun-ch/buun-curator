"use client";

import { FolderTree, Languages, Rss, Tags, X } from "lucide-react";
import * as React from "react";

import { Button } from "@/components/ui/button";
import type { SettingsCategory as SettingsCategoryType } from "@/lib/navigation";
import { useUrlState } from "@/lib/url-state-context";
import { cn } from "@/lib/utils";

export interface SettingsCategory {
  id: SettingsCategoryType;
  title: string;
  icon: React.ReactNode;
  description?: string;
}

interface SettingsNavProps {
  onClose?: () => void;
}

// Settings categories
const settingsCategories: SettingsCategory[] = [
  {
    id: "categories",
    title: "Categories",
    icon: <FolderTree className="size-4" />,
    description: "Manage feed categories",
  },
  {
    id: "feeds",
    title: "Feeds",
    icon: <Rss className="size-4" />,
    description: "Manage your feed subscriptions",
  },
  {
    id: "labels",
    title: "Labels",
    icon: <Tags className="size-4" />,
    description: "Manage entry labels",
  },
  {
    id: "language",
    title: "Language",
    icon: <Languages className="size-4" />,
    description: "Translation and language settings",
  },
];

export function SettingsNav({ onClose }: SettingsNavProps) {
  const { settingsCategory, navigateToSettings } = useUrlState();

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center border-b px-4">
        <h2 className="flex-1 text-sm font-semibold select-none">Settings</h2>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onClose}
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Category list */}
      <div className="flex-1 overflow-auto">
        <nav className="flex flex-col gap-1 p-2">
          {settingsCategories.map((category) => (
            <button
              key={category.id}
              onClick={() => navigateToSettings(category.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition-colors hover:bg-accent",
                settingsCategory === category.id && "bg-accent font-medium",
              )}
            >
              {category.icon}
              <span className="select-none">{category.title}</span>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}

export { settingsCategories };
