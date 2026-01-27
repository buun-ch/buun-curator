"use client";

/**
 * Mobile settings view component.
 *
 * Full-screen settings for mobile navigation.
 *
 * @module components/reader/mobile/settings-view
 */

import { motion } from "framer-motion";
import { ChevronLeft } from "lucide-react";

import { CategoriesSettings } from "@/components/settings/categories-settings";
import { FeedsSettings } from "@/components/settings/feeds-settings";
import { LabelsSettings } from "@/components/settings/labels-settings";
import { LanguageSettings } from "@/components/settings/language-settings";
import { settingsCategories } from "@/components/settings/settings-nav";
import { Button } from "@/components/ui/button";
import type { SettingsCategory } from "@/lib/navigation";
import { useUrlState } from "@/lib/url-state-context";
import { cn } from "@/lib/utils";
import { useMobileNavStore } from "@/stores/mobile-nav-store";

/** Props for MobileSettingsView. */
interface MobileSettingsViewProps {
  /** Callback when back button is pressed. */
  onBack: () => void;
}

/**
 * Slide animation variants with direction support.
 * Custom value is direction: 1 = push (forward), -1 = pop (backward).
 */
const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? "100%" : "-100%",
    opacity: 0,
  }),
  center: { x: 0, opacity: 1 },
  exit: (direction: number) => ({
    x: direction > 0 ? "-100%" : "100%",
    opacity: 0,
  }),
};

/** Renders settings content based on category. */
function SettingsContent({ categoryId }: { categoryId: SettingsCategory }) {
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
}

/**
 * Mobile settings view with back navigation.
 */
export function MobileSettingsView({ onBack }: MobileSettingsViewProps) {
  const direction = useMobileNavStore((state) => state.direction);
  const { settingsCategory, navigateToSettings } = useUrlState();
  const category = settingsCategories.find((c) => c.id === settingsCategory);

  return (
    <motion.div
      className="absolute inset-0 flex flex-col bg-background"
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ type: "tween", duration: 0.25, ease: "easeInOut" }}
    >
      {/* Header */}
      <div className="flex h-12 shrink-0 items-center gap-2 border-b px-2">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1 px-2"
          onClick={onBack}
        >
          <ChevronLeft className="size-4" />
        </Button>
        <h2 className="flex-1 text-sm font-semibold select-none">
          {category?.title || "Settings"}
        </h2>
      </div>

      {/* Settings Navigation Tabs */}
      <div className="flex w-full justify-center border-b">
        <nav className="px-2 py-1">
          {settingsCategories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => navigateToSettings(cat.id)}
              className={cn(
                "inline-block rounded-md px-3 py-2 text-sm transition-colors",
                {
                  "bg-accent font-medium": settingsCategory === cat.id,
                  "hover:bg-accent/50": settingsCategory !== cat.id,
                },
              )}
            >
              {cat.icon}
            </button>
          ))}
        </nav>
      </div>

      {/* Settings Content */}
      <div className="flex-1 overflow-auto">
        <div className="px-4 py-6">
          <SettingsContent categoryId={settingsCategory ?? "categories"} />
        </div>
      </div>
    </motion.div>
  );
}
