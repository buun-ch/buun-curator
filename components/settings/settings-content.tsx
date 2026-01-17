"use client";

import { FixedWidthPanel } from "@/components/ui/fixed-width-panel";
import { SettingsNav } from "@/components/settings/settings-nav";
import { SettingsPanel } from "@/components/settings/settings-panel";
import { useSettingsStore } from "@/stores/settings-store";
import { useUrlState } from "@/lib/url-state-context";

/** Settings content with navigation and panel. */
export function SettingsContent() {
  const { navigateToAllEntries, settingsCategory } = useUrlState();
  const settingsNavPanelWidth = useSettingsStore(
    (state) => state.settingsNavPanelWidth
  );
  const setSettingsNavPanelWidth = useSettingsStore(
    (state) => state.setSettingsNavPanelWidth
  );

  const handleClose = () => {
    navigateToAllEntries();
  };

  return (
    <>
      {/* Settings Navigation */}
      <FixedWidthPanel
        width={settingsNavPanelWidth}
        onWidthChange={setSettingsNavPanelWidth}
        minWidth={150}
        maxWidth={400}
        className="h-full"
      >
        <SettingsNav onClose={handleClose} />
      </FixedWidthPanel>

      {/* Settings Panel - fills remaining space */}
      <div className="flex min-w-0 flex-1 flex-col">
        <SettingsPanel categoryId={settingsCategory} onClose={handleClose} />
      </div>
    </>
  );
}
