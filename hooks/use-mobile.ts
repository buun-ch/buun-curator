/**
 * Hook for detecting mobile viewport.
 *
 * Uses matchMedia to detect viewport width and update on resize.
 *
 * @module hooks/use-mobile
 */

import * as React from "react";

/** Mobile breakpoint width in pixels. */
const MOBILE_BREAKPOINT = 768;

/**
 * Hook for detecting mobile viewport.
 *
 * Returns true when viewport width is less than 768px.
 * Listens for resize events and updates automatically.
 *
 * @returns True if viewport is mobile-sized
 */
export function useIsMobile() {
  const [isMobile, setIsMobile] = React.useState<boolean | undefined>(
    undefined,
  );

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    };
    mql.addEventListener("change", onChange);
    setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return !!isMobile;
}
