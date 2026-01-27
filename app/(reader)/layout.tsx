import { NuqsAdapter } from "nuqs/adapters/next/app";
import { Suspense } from "react";

import { UrlStateProvider } from "@/lib/url-state-context";

/** Layout for reader routes with URL state management. */
export default function ReaderGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <NuqsAdapter>
      <Suspense fallback={null}>
        <UrlStateProvider>{children}</UrlStateProvider>
      </Suspense>
    </NuqsAdapter>
  );
}
