/**
 * Application configuration utilities.
 *
 * This module provides centralized access to configuration values.
 * Public environment variables are handled by lib/env.ts using next-public-env,
 * which enables runtime configuration (build once, deploy many).
 *
 * @module lib/config
 */

import { NextResponse } from "next/server";
import { getPublicEnv } from "./env";

// Re-export for convenience
export { getPublicEnv, PublicEnv } from "./env";
export type { PublicEnvType } from "./env";

/**
 * Returns whether authentication is enabled.
 *
 * Defaults to true if not explicitly set to "false".
 */
export function isAuthEnabled(): boolean {
  return getPublicEnv().AUTH_ENABLED;
}

/**
 * Returns whether Reddit features are enabled.
 *
 * Only returns true if explicitly set to "true".
 */
export function isRedditEnabled(): boolean {
  return getPublicEnv().REDDIT_ENABLED;
}

/**
 * Returns whether SSE debug UI is enabled.
 *
 * Only returns true if explicitly set to "true".
 */
export function isDebugSSEEnabled(): boolean {
  return getPublicEnv().DEBUG_SSE;
}

/**
 * Returns whether research context feature is enabled.
 *
 * Only returns true if explicitly set to "true".
 */
export function isResearchContextEnabled(): boolean {
  return getPublicEnv().RESEARCH_CONTEXT_ENABLED;
}

/**
 * Returns a 403 response if Reddit features are disabled.
 *
 * Use this as a guard at the beginning of Reddit API route handlers.
 *
 * @returns NextResponse with 403 status if Reddit is disabled, null otherwise
 */
export function checkRedditEnabled(): NextResponse | null {
  if (!isRedditEnabled()) {
    return NextResponse.json(
      { error: "Reddit features are disabled" },
      { status: 403 }
    );
  }
  return null;
}
