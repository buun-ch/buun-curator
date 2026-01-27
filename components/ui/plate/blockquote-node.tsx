"use client";

import { PlateElement, type PlateElementProps } from "platejs/react";

// Styles matching Tailwind Typography `prose` defaults
export function BlockquoteElement(props: PlateElementProps) {
  return (
    <PlateElement
      as="blockquote"
      className="font-italic my-[1.6em] border-l-[0.25rem] border-current pl-[1em] text-inherit"
      {...props}
    />
  );
}
