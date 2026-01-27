"use client";

import * as React from "react";

import { cn } from "@/lib/utils";

interface FixedWidthPanelProps {
  children: React.ReactNode;
  width: number;
  onWidthChange: (width: number) => void;
  minWidth?: number;
  maxWidth?: number;
  className?: string;
  /** Position of the resize handle. */
  handlePosition?: "left" | "right";
}

/**
 * A panel with a fixed pixel width that can be resized by dragging.
 * Unlike react-resizable-panels, this uses absolute pixel widths
 * so the panel doesn't resize when the window is resized.
 */
export function FixedWidthPanel({
  children,
  width,
  onWidthChange,
  minWidth = 100,
  maxWidth = 600,
  className,
  handlePosition = "right",
}: FixedWidthPanelProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const panelRef = React.useRef<HTMLDivElement>(null);
  const startXRef = React.useRef(0);
  const startWidthRef = React.useRef(0);

  // Calculate effective max width based on window size (max 50% of window)
  const getEffectiveMaxWidth = React.useCallback(() => {
    if (typeof window === "undefined") return maxWidth;
    return Math.min(maxWidth, window.innerWidth * 0.5);
  }, [maxWidth]);

  const handleMouseDown = React.useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);
      startXRef.current = e.clientX;
      startWidthRef.current = width;
    },
    [width],
  );

  React.useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const effectiveMax = getEffectiveMaxWidth();
      const delta =
        handlePosition === "right"
          ? e.clientX - startXRef.current
          : startXRef.current - e.clientX;
      const newWidth = Math.min(
        effectiveMax,
        Math.max(minWidth, startWidthRef.current + delta),
      );
      onWidthChange(newWidth);
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
  }, [
    isDragging,
    handlePosition,
    minWidth,
    getEffectiveMaxWidth,
    onWidthChange,
  ]);

  // Clamp width when window is resized
  React.useEffect(() => {
    const handleResize = () => {
      const effectiveMax = getEffectiveMaxWidth();
      if (width > effectiveMax) {
        onWidthChange(effectiveMax);
      }
    };

    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, [width, getEffectiveMaxWidth, onWidthChange]);

  return (
    <div
      ref={panelRef}
      className={cn("relative flex shrink-0", className)}
      style={{ width }}
    >
      {handlePosition === "left" && (
        <ResizeHandle onMouseDown={handleMouseDown} isDragging={isDragging} />
      )}
      <div className="flex-1 overflow-hidden">{children}</div>
      {handlePosition === "right" && (
        <ResizeHandle onMouseDown={handleMouseDown} isDragging={isDragging} />
      )}
    </div>
  );
}

interface ResizeHandleProps {
  onMouseDown: (e: React.MouseEvent) => void;
  isDragging: boolean;
}

function ResizeHandle({ onMouseDown, isDragging }: ResizeHandleProps) {
  return (
    <div
      onMouseDown={onMouseDown}
      className={cn(
        "relative flex w-px cursor-col-resize items-center justify-center bg-border",
        "after:absolute after:inset-y-0 after:left-1/2 after:w-1 after:-translate-x-1/2",
        "transition-colors hover:bg-primary/50",
        isDragging && "bg-primary",
      )}
    >
      <div className="z-10 flex h-4 w-3 items-center justify-center rounded-sm border bg-border" />
    </div>
  );
}
