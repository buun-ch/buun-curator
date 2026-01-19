'use client';

import { type PlateElementProps, PlateElement } from 'platejs/react';

// Styles matching Tailwind Typography `prose` defaults
export function BlockquoteElement(props: PlateElementProps) {
  return (
    <PlateElement
      as="blockquote"
      className="my-[1.6em] border-l-[0.25rem] border-current pl-[1em] font-italic text-inherit"
      {...props}
    />
  );
}
