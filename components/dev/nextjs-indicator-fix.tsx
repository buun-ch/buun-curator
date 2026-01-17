"use client";

import { useEffect } from "react";

/**
 * Adjusts the position of Next.js Dev Indicator in development mode.
 * The indicator is rendered inside a Shadow DOM (nextjs-portal),
 * so we need to use JavaScript to modify its position.
 */
export function NextjsIndicatorFix() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "development") return;

    const adjustPosition = () => {
      const portal = document.querySelector("nextjs-portal");
      if (!portal?.shadowRoot) return;

      const indicator = portal.shadowRoot.getElementById("devtools-indicator");
      if (indicator) {
        indicator.style.right = "auto";
        indicator.style.left = "50%";
        indicator.style.bottom = "24px";
        // Center with offset to the left (React Query DevTools is on the right)
        indicator.style.transform = "translateX(calc(-50% + 25px))";
      }
    };

    // Initial adjustment
    adjustPosition();

    // Observe for changes (indicator may be added dynamically)
    const observer = new MutationObserver(adjustPosition);
    observer.observe(document.body, { childList: true, subtree: true });

    return () => observer.disconnect();
  }, []);

  return null;
}
