"use client";

/**
 * Mobile viewer view component.
 *
 * Full-screen entry viewer with back navigation for mobile.
 *
 * @module components/reader/mobile/viewer-view
 */

import { motion } from "framer-motion";
import * as React from "react";

import {
  ContentViewer,
  type ContentViewerProps,
  type ContentViewerRef,
} from "@/components/reader/content-viewer";
import { useMobileNavStore } from "@/stores/mobile-nav-store";

/** Props for MobileViewerView. */
interface MobileViewerViewProps extends ContentViewerProps {
  /** Callback when back button is pressed. */
  onBack: () => void;
  /** Ref to ContentViewer for scroll control. */
  viewerRef?: React.Ref<ContentViewerRef>;
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
 * Mobile viewer view with back navigation.
 */
export function MobileViewerView({
  onBack,
  viewerRef,
  ...contentViewerProps
}: MobileViewerViewProps) {
  const direction = useMobileNavStore((state) => state.direction);

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
      {/* Content viewer with back button in toolbar */}
      <ContentViewer ref={viewerRef} onBack={onBack} {...contentViewerProps} />
    </motion.div>
  );
}
