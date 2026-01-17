/**
 * Hook to detect if the app has been hydrated on the client.
 *
 * Returns false during SSR and initial client render, true after hydration.
 * Use this to prevent hydration mismatches when using persisted state that
 * affects conditional rendering.
 *
 * @module hooks/use-hydrated
 */

"use client";

import { useEffect, useState } from "react";

/**
 * Detect if the component has been hydrated.
 *
 * Uses useEffect to ensure the first client render matches the server render,
 * preventing hydration mismatches with Radix UI components that use useId().
 *
 * @returns true if running on the client after hydration, false otherwise
 */
export function useHydrated(): boolean {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // Intentionally trigger re-render after hydration to sync persisted state.
    // This is the standard pattern for hydration detection.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHydrated(true);
  }, []);

  return hydrated;
}
