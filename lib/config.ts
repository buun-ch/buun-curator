/**
 * Application configuration utilities.
 *
 * @module lib/config
 */

import { NextResponse } from "next/server";

/**
 * Returns whether Reddit features are enabled.
 *
 * Checks the NEXT_PUBLIC_REDDIT_ENABLED environment variable.
 * Only returns true if explicitly set to "true".
 */
export function isRedditEnabled(): boolean {
  return process.env.NEXT_PUBLIC_REDDIT_ENABLED === "true";
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
