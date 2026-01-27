import type { SlateElementProps } from "platejs/static";
import { SlateElement } from "platejs/static";
import * as React from "react";

import { cn } from "@/lib/utils";

export function HrElementStatic(props: SlateElementProps) {
  return (
    <SlateElement {...props} className="my-4">
      <div className="cursor-text py-1" contentEditable={false}>
        <hr
          className={cn(
            "!my-0 h-0.5 rounded-sm border-none bg-muted bg-clip-content",
          )}
        />
      </div>
      {props.children}
    </SlateElement>
  );
}
