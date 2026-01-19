'use client';

import * as React from 'react';

import type { PlateElementProps } from 'platejs/react';

import { type VariantProps, cva } from 'class-variance-authority';
import { PlateElement } from 'platejs/react';

// Styles matching Tailwind Typography `prose` defaults
const headingVariants = cva('relative font-bold', {
  variants: {
    variant: {
      h1: 'mb-[0.8888889em] text-[2.25em] leading-[1.1111111]',
      h2: 'mt-[1.3333333em] mb-[0.6666667em] text-[1.5em] leading-[1.3333333]',
      h3: 'mt-[1.6em] mb-[0.6em] text-[1.25em] leading-[1.6]',
      h4: 'mt-[1.5em] mb-[0.5em] text-[1em] leading-[1.5]',
      h5: 'mt-[1.5em] mb-[0.5em] text-[1em] leading-[1.5]',
      h6: 'mt-[1.5em] mb-[0.5em] text-[1em] leading-[1.5]',
    },
  },
});

export function HeadingElement({
  variant = 'h1',
  ...props
}: PlateElementProps & VariantProps<typeof headingVariants>) {
  return (
    <PlateElement
      as={variant!}
      className={headingVariants({ variant })}
      {...props}
    >
      {props.children}
    </PlateElement>
  );
}

export function H1Element(props: PlateElementProps) {
  return <HeadingElement variant="h1" {...props} />;
}

export function H2Element(props: PlateElementProps) {
  return <HeadingElement variant="h2" {...props} />;
}

export function H3Element(props: PlateElementProps) {
  return <HeadingElement variant="h3" {...props} />;
}

export function H4Element(props: PlateElementProps) {
  return <HeadingElement variant="h4" {...props} />;
}

export function H5Element(props: PlateElementProps) {
  return <HeadingElement variant="h5" {...props} />;
}

export function H6Element(props: PlateElementProps) {
  return <HeadingElement variant="h6" {...props} />;
}
