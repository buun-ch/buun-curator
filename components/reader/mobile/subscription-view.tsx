"use client";

/**
 * Mobile subscription view component.
 *
 * Full-screen subscription sidebar for mobile navigation.
 *
 * @module components/reader/mobile/subscription-view
 */

import { motion } from "framer-motion";

import { SubscriptionSidebar } from "@/components/reader/subscription-sidebar";
import { useMobileNavStore } from "@/stores/mobile-nav-store";

/** Props for MobileSubscriptionView. */
interface MobileSubscriptionViewProps {
  /** Callback when entries fetch completes. */
  onFetchNewComplete?: () => Promise<void>;
  /** Callback when a subscription is selected. */
  onSubscriptionSelect?: (id: string) => void;
  /** Callback when settings is clicked. */
  onSettingsClick?: () => void;
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

/**
 * Mobile subscription view displaying full-screen sidebar.
 */
export function MobileSubscriptionView({
  onFetchNewComplete,
  onSubscriptionSelect,
  onSettingsClick,
}: MobileSubscriptionViewProps) {
  const direction = useMobileNavStore((state) => state.direction);

  return (
    <motion.div
      className="absolute inset-0 bg-background"
      custom={direction}
      variants={slideVariants}
      initial="enter"
      animate="center"
      exit="exit"
      transition={{ type: "tween", duration: 0.25, ease: "easeInOut" }}
    >
      <SubscriptionSidebar
        collapsed={false}
        viewMode="reader"
        onFetchNewComplete={onFetchNewComplete}
        onSubscriptionSelect={onSubscriptionSelect}
        onSettingsClick={onSettingsClick}
      />
    </motion.div>
  );
}
