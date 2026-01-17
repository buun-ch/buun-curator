"use client";

import * as React from "react";

import { useSettingsStore } from "@/stores/settings-store";

import { MIN_HEIGHT, MAX_HEIGHT, DEFAULT_HEIGHT } from "../constants";

interface UsePanelResizeResult {
  height: number;
  isDragging: boolean;
  handleMouseDown: (e: React.MouseEvent) => void;
}

/**
 * Hook for managing panel resize behavior.
 *
 * @returns Panel height, dragging state, and mouse handler
 */
export function usePanelResize(): UsePanelResizeResult {
  const height = useSettingsStore(
    (state) => state.contextPanelHeight ?? DEFAULT_HEIGHT
  );
  const setHeight = useSettingsStore((state) => state.setContextPanelHeight);

  const [isDragging, setIsDragging] = React.useState(false);
  const startYRef = React.useRef(0);
  const startHeightRef = React.useRef(0);

  // Calculate effective max height based on window size (max 70% of window)
  const getEffectiveMaxHeight = React.useCallback(() => {
    if (typeof window === "undefined") return MAX_HEIGHT;
    return Math.min(MAX_HEIGHT, window.innerHeight * 0.7);
  }, []);

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);
      startYRef.current = e.clientY;
      startHeightRef.current = height;
    },
    [height]
  );

  React.useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const effectiveMax = getEffectiveMaxHeight();
      // Dragging up increases height (negative delta)
      const delta = startYRef.current - e.clientY;
      const newHeight = Math.min(
        effectiveMax,
        Math.max(MIN_HEIGHT, startHeightRef.current + delta)
      );
      setHeight(newHeight);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, getEffectiveMaxHeight, setHeight]);

  // Clamp height when window is resized
  React.useEffect(() => {
    const handleResize = () => {
      const effectiveMax = getEffectiveMaxHeight();
      if (height > effectiveMax) {
        setHeight(effectiveMax);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [height, getEffectiveMaxHeight, setHeight]);

  return {
    height,
    isDragging,
    handleMouseDown,
  };
}
