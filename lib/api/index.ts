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
  ExtractionRuleType,
  ExtractionRule,
  FeedOptions,
  ErrorResult,
  SuccessResult,
  Result,
} from "./types";
export { DEFAULT_FETCH_LIMIT, MAX_FETCH_LIMIT, isError } from "./types";

// Feed functions
export { listFeeds, getFeed, updateFeedChecked, saveExtractionRule } from "./feeds";

// Entry functions
export {
  getEntry,
  createEntry,
  updateEntry,
  listEntries,
} from "./entries";

// Extraction functions
export type {
  SelectorCandidate,
  FindElementResult,
  PreviewExclusionResult,
} from "./extraction";
export { findElementByText, previewExclusion } from "./extraction";

// Settings functions
export type { AppSettings } from "./settings";
export { getSettings } from "./settings";
