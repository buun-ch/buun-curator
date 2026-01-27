/**
 * Hook for detecting responsive layout mode.
 *
 * Provides three layout modes based on viewport width:
 * - mobile: < 430px (iPhone Portrait)
 * - compact: 430px - 1023px (iPhone Landscape, iPad Portrait)
 * - desktop: >= 1024px (iPad Landscape, PC)
 *
 * @module hooks/use-layout-mode
 */

import * as React from "react";

/** Layout mode based on viewport width. */
export type LayoutMode = "mobile" | "compact" | "desktop";

/** Breakpoint for mobile mode (exclusive upper bound). */
const MOBILE_BREAKPOINT = 430;

/** Breakpoint for compact mode (exclusive upper bound). */
const COMPACT_BREAKPOINT = 1024;

/**
 * Determines layout mode from viewport width.
 */
function getLayoutMode(width: number): LayoutMode {
  if (width < MOBILE_BREAKPOINT) return "mobile";
  if (width < COMPACT_BREAKPOINT) return "compact";
  return "desktop";
}

/**
 * Hook for detecting current layout mode.
 *
 * Returns null during SSR and initial render, then updates to actual mode.
 * Components should treat null as "desktop" for SSR compatibility.
 *
 * @returns Current layout mode, or null during SSR/initial render
 */
export function useLayoutMode(): LayoutMode | null {
  const [layoutMode, setLayoutMode] = React.useState<LayoutMode | null>(null);

  React.useEffect(() => {
    const updateMode = () => {
      setLayoutMode(getLayoutMode(window.innerWidth));
    };

    // Set initial value
    updateMode();

    // Listen for resize events
    const mediaQueryMobile = window.matchMedia(
      `(max-width: ${MOBILE_BREAKPOINT - 1}px)`,
    );
    const mediaQueryCompact = window.matchMedia(
      `(min-width: ${MOBILE_BREAKPOINT}px) and (max-width: ${COMPACT_BREAKPOINT - 1}px)`,
    );

    mediaQueryMobile.addEventListener("change", updateMode);
    mediaQueryCompact.addEventListener("change", updateMode);

    return () => {
      mediaQueryMobile.removeEventListener("change", updateMode);
      mediaQueryCompact.removeEventListener("change", updateMode);
    };
  }, []);

  return layoutMode;
}

/**
 * Hook for detecting mobile layout mode.
 *
 * Returns false during SSR/initial render.
 *
 * @returns True if layout mode is mobile
 */
export function useIsMobile(): boolean {
  return useLayoutMode() === "mobile";
}

/**
 * Hook for detecting compact layout mode.
 *
 * Returns false during SSR/initial render.
 *
 * @returns True if layout mode is compact
 */
export function useIsCompact(): boolean {
  return useLayoutMode() === "compact";
}

/**
 * Hook for detecting desktop layout mode.
 *
 * Returns false during SSR/initial render (null !== "desktop").
 *
 * @returns True if layout mode is desktop
 */
export function useIsDesktop(): boolean {
  return useLayoutMode() === "desktop";
}
