/**
 * Internal API types and utilities.
 *
 * This module provides shared types used across the internal API layer
 * that is consumed by both REST API routes and MCP handlers.
 *
 * @module lib/api/types
 */

import { db as defaultDb } from "@/db";

/** Database instance type for dependency injection. */
export type Db = typeof defaultDb;

/** Supported extraction rule types for content filtering. */
export type ExtractionRuleType = "css_selector" | "xpath";

/** Rule for extracting/excluding content from fetched articles. */
export interface ExtractionRule {
  /** Type of selector to use. */
  type: ExtractionRuleType;
  /** The selector value (CSS selector or XPath expression). */
  value: string;
  /** Optional human-readable description of what this rule does. */
  description?: string;
  /** ISO timestamp of when the rule was created. */
  createdAt?: string;
}

/** Per-feed configuration options stored in the feed's options JSON field. */
export interface FeedOptions {
  /** List of extraction rules for content filtering. */
  extractionRules?: ExtractionRule[];
}

/** Default number of entries to fetch when not specified. */
export const DEFAULT_FETCH_LIMIT = 20;

/** Maximum allowed fetch limit to prevent excessive queries. */
export const MAX_FETCH_LIMIT = 100;

/** Standard error result for API functions that can fail. */
export interface ErrorResult {
  /** Human-readable error message. */
  error: string;
  /** Additional error context (e.g., existingEntryId for duplicates). */
  [key: string]: unknown;
}

/** Standard success result for API functions. */
export interface SuccessResult {
  /** Indicates successful operation. */
  success: true;
  /** Additional result data. */
  [key: string]: unknown;
}

/** Union type for functions that return either success data or an error. */
export type Result<T> = T | ErrorResult;

/**
 * Type guard to check if a result is an error.
 *
 * @param result - The result to check
 * @returns True if the result contains an error property
 */
export function isError(result: unknown): result is ErrorResult {
  return (
    typeof result === "object" &&
    result !== null &&
    "error" in result &&
    typeof (result as ErrorResult).error === "string"
  );
}
