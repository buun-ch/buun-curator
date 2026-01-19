"use client";

import { Globe, Languages, Columns2 } from "lucide-react";

import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import type { LanguageMode } from "@/lib/types";

interface LanguageToggleProps {
  value: LanguageMode;
  onChange: (mode: LanguageMode) => void;
}

/**
 * Language toggle component.
 *
 * Allows switching between original, translated, and side-by-side views.
 */
export function LanguageToggle({ value, onChange }: LanguageToggleProps) {
  return (
    <div className="mb-6 flex items-center justify-center gap-2">
      <div className="h-px flex-1 bg-border" />
      <ToggleGroup
        type="single"
        value={value}
        onValueChange={(newValue) =>
          newValue && onChange(newValue as LanguageMode)
        }
        variant="outline"
        size="sm"
      >
        <ToggleGroupItem
          value="original"
          aria-label="Original language"
          className="size-5 p-3.5"
        >
          <Globe className="size-3.5" />
        </ToggleGroupItem>
        <ToggleGroupItem
          value="translated"
          aria-label="Translated"
          className="size-5 p-3.5"
        >
          <Languages className="size-3.5" />
        </ToggleGroupItem>
        <ToggleGroupItem
          value="both"
          aria-label="Side by side"
          className="size-5 p-3.5"
        >
          <Columns2 className="size-3.5" />
        </ToggleGroupItem>
      </ToggleGroup>
      <div className="h-px flex-1 bg-border" />
    </div>
  );
}
