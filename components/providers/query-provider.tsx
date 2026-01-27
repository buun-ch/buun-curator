"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import * as React from "react";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Data is considered fresh for 5 minutes
        staleTime: 5 * 60 * 1000,
        // Keep unused data in cache for 30 minutes
        gcTime: 30 * 60 * 1000,
        // Retry failed requests once
        retry: 1,
        // Don't refetch on window focus by default
        refetchOnWindowFocus: false,
      },
    },
  });
}

let browserQueryClient: QueryClient | undefined = undefined;

function getQueryClient() {
  if (typeof window === "undefined") {
    // Server: always make a new query client
    return makeQueryClient();
  } else {
    // Browser: make a new query client if we don't already have one
    if (!browserQueryClient) browserQueryClient = makeQueryClient();
    return browserQueryClient;
  }
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const queryClient = getQueryClient();

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools
        initialIsOpen={false}
        buttonPosition="bottom-right"
        styleNonce="rq-devtools"
      />
      <style>{`
        .tsqd-open-btn-container { left: 50% !important; right: auto !important; bottom: 19px !important; transform: translateX(calc(-50% - 25px)) scale(0.82); }
      `}</style>
    </QueryClientProvider>
  );
}
