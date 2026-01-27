"use client";

/**
 * Mobile list view component.
 *
 * Full-screen entry list with back navigation for mobile.
 *
 * @module components/reader/mobile/list-view
 */

import { motion } from "framer-motion";

import type { ContentListProps } from "@/components/reader/content-list";
import { ContentList } from "@/components/reader/content-list";
import { useSelectedSubscriptionInfo } from "@/hooks/use-selected-subscription-info";
import { useMobileNavStore } from "@/stores/mobile-nav-store";

/** Props for MobileListView. */
interface MobileListViewProps extends ContentListProps {
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

/**
 * Mobile list view with back navigation.
 *
 * Back button is rendered inside ContentList's ListHeader.
 */
export function MobileListView({
  onBack,
  ...contentListProps
}: MobileListViewProps) {
  const { info: subscriptionInfo } = useSelectedSubscriptionInfo();
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
      <ContentList
        {...contentListProps}
        subscriptionInfo={subscriptionInfo}
        onBack={onBack}
      />
    </motion.div>
  );
}
