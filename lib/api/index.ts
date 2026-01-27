/**
 * Internal API module.
 *
 * This module provides the core database operations used by both
 * REST API routes and MCP handlers. All functions accept an optional
 * database instance for testability.
 *
 * @module lib/api
 */

// Types
export type {
  Db,
  ErrorResult,
  ExtractionRule,
  ExtractionRuleType,
  FeedOptions,
  Result,
  SuccessResult,
} from "./types";
export { DEFAULT_FETCH_LIMIT, isError, MAX_FETCH_LIMIT } from "./types";

// Feed functions
export {
  getFeed,
  listFeeds,
  saveExtractionRule,
  updateFeedChecked,
} from "./feeds";

// Entry functions
export { createEntry, getEntry, listEntries, updateEntry } from "./entries";

// Extraction functions
export type {
  FindElementResult,
  PreviewExclusionResult,
  SelectorCandidate,
} from "./extraction";
export { findElementByText, previewExclusion } from "./extraction";

// Settings functions
export type { AppSettings } from "./settings";
export { getSettings } from "./settings";
