/**
 * Public environment configuration using next-public-env.
 *
 * This module provides runtime access to public environment variables
 * that work in both Server and Client Components.
 *
 * Usage:
 * - Add `<PublicEnv />` to root layout (app/layout.tsx)
 * - Use `getPublicEnv()` to access variables anywhere
 *
 * @module lib/env
 */

import { createPublicEnv } from "next-public-env";

/**
 * Public environment variables exposed to the client.
 *
 * These are read at runtime (not build time), enabling
 * "build once, deploy many" with different configurations.
 */
export const { getPublicEnv, PublicEnv } = createPublicEnv(
  {
    AUTH_ENABLED: process.env.NEXT_PUBLIC_AUTH_ENABLED,
    DEBUG_SSE: process.env.NEXT_PUBLIC_DEBUG_SSE,
    REDDIT_ENABLED: process.env.NEXT_PUBLIC_REDDIT_ENABLED,
    RESEARCH_CONTEXT_ENABLED: process.env.NEXT_PUBLIC_RESEARCH_CONTEXT_ENABLED,
  },
  {
    schema: (z) => ({
      /** Whether authentication is enabled. Defaults to true if not set. */
      AUTH_ENABLED: z
        .enum(["true", "false"])
        .default("true")
        .transform((v) => v === "true"),
      /** Whether SSE debug UI is enabled. Defaults to false. */
      DEBUG_SSE: z
        .enum(["true", "false"])
        .default("false")
        .transform((v) => v === "true"),
      /** Whether Reddit features are enabled. Defaults to false. */
      REDDIT_ENABLED: z
        .enum(["true", "false"])
        .default("false")
        .transform((v) => v === "true"),
      /** Whether research context feature is enabled. Defaults to false. */
      RESEARCH_CONTEXT_ENABLED: z
        .enum(["true", "false"])
        .default("false")
        .transform((v) => v === "true"),
    }),
  },
);

/** Type for public environment variables. */
export type PublicEnvType = ReturnType<typeof getPublicEnv>;
