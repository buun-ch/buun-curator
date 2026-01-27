"use client";

import type { PlateElementProps } from "platejs/react";
import { PlateElement } from "platejs/react";
import * as React from "react";

import { cn } from "@/lib/utils";

export function ParagraphElement(props: PlateElementProps) {
  return (
    <PlateElement {...props} className={cn("my-[1.25em]")}>
      {props.children}
    </PlateElement>
  );
}
