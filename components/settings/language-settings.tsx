"use client";

import { Loader2 } from "lucide-react";
import * as React from "react";

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
const TARGET_LANGUAGES = [
  { value: "__none__", label: "(no translation)" },
  { value: "zh", label: "Chinese (Simplified)" },
  { value: "en", label: "English" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "pt", label: "Portuguese" },
  { value: "es", label: "Spanish" },
] as const;

export function LanguageSettings() {
  const [targetLanguage, setTargetLanguage] =
    React.useState<string>("__none__");
  const [loading, setLoading] = React.useState(true);
  const [saving, setSaving] = React.useState(false);

  // Load settings from API
  React.useEffect(() => {
    const fetchSettings = async () => {
      try {
        const response = await fetch("/api/settings");
        if (response.ok) {
          const data = await response.json();
          setTargetLanguage(data.targetLanguage ?? "__none__");
        }
      } catch (error) {
        console.error("Failed to fetch settings:", error);
      } finally {
        setLoading(false);
      }
    };
    fetchSettings();
  }, []);

  // Save setting to API
  const handleTargetLanguageChange = async (value: string) => {
    setTargetLanguage(value);
    setSaving(true);
    try {
      await fetch("/api/settings", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          targetLanguage: value === "__none__" ? "" : value,
        }),
      });
    } catch (error) {
      console.error("Failed to save settings:", error);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Translation Section */}
      <section className="space-y-6">
        <div className="space-y-2">
          <h3 className="text-lg font-medium">Translation</h3>
          <p className="text-sm text-muted-foreground">
            Configure translation settings.
          </p>
        </div>

        {/* Target Language */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Target Language</label>
          <p className="text-sm text-muted-foreground">
            Entries will be translated into this language.
          </p>
          <div className="flex items-center gap-2">
            <Select
              value={targetLanguage}
              onValueChange={handleTargetLanguageChange}
              disabled={saving}
            >
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="Select language" />
              </SelectTrigger>
              <SelectContent>
                {TARGET_LANGUAGES.map((lang) => (
                  <SelectItem key={lang.value} value={lang.value}>
                    {lang.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {saving && (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
