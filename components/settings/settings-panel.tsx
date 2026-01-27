"use client";

import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { SettingsCategory } from "@/lib/navigation";

import { CategoriesSettings } from "./categories-settings";
import { FeedsSettings } from "./feeds-settings";
import { LabelsSettings } from "./labels-settings";
import { LanguageSettings } from "./language-settings";
import { settingsCategories } from "./settings-nav";

interface SettingsPanelProps {
  categoryId?: SettingsCategory;
  onClose?: () => void;
}

export function SettingsPanel({
  categoryId = "categories",
  onClose,
}: SettingsPanelProps) {
  const category = settingsCategories.find((c) => c.id === categoryId);

  const renderContent = () => {
    switch (categoryId) {
      case "categories":
        return <CategoriesSettings />;
      case "feeds":
        return <FeedsSettings />;
      case "labels":
        return <LabelsSettings />;
      case "language":
        return <LanguageSettings />;
      default:
        return <CategoriesSettings />;
    }
  };

  return (
    <div className="flex h-full flex-col bg-background">
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center border-b px-6">
        <h2 className="flex-1 text-sm font-semibold select-none">
          {category?.title || "Settings"}
        </h2>
        <Button
          variant="ghost"
          size="icon"
          className="size-8"
          onClick={onClose}
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-2xl px-6 py-8">{renderContent()}</div>
      </div>
    </div>
  );
}
