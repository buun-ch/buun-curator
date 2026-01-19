/**
 * Feed discovery utilities for finding RSS/Atom feeds from URLs.
 *
 * Supports multiple discovery methods:
 * - Direct feed URL detection
 * - HTML link tag extraction
 * - Common feed path probing
 *
 * @module lib/feed-discovery
 */

import { parseHTML } from "linkedom";
import { createLogger } from "@/lib/logger";

const log = createLogger("feed-discovery");

/** A discovered feed with its URL and metadata. */
export interface DiscoveredFeed {
  /** Absolute URL of the feed. */
  url: string;
  /** Feed title if available. */
  title?: string;
  /** Detected feed type. */
  type: "rss" | "atom" | "unknown";
}

/** HTTP error information. */
export interface HttpError {
  /** HTTP status code. */
  status: number;
  /** HTTP status text. */
  statusText: string;
}

/** Result of feed discovery for a URL. */
export interface FeedDiscoveryResult {
  /** List of discovered feeds. */
  feeds: DiscoveredFeed[];
  /** Site title from HTML if available. */
  siteTitle?: string;
  /** Base site URL (origin). */
  siteUrl: string;
  /** HTTP error if the request failed. */
  httpError?: HttpError;
}

/** Content types that indicate a feed response. */
const FEED_CONTENT_TYPES = [
  "application/rss+xml",
  "application/atom+xml",
  "application/xml",
  "text/xml",
  "application/feed+json",
  "application/json",
];

/** Link rel types to search for in HTML head. */
const FEED_LINK_TYPES = [
  "application/rss+xml",
  "application/atom+xml",
  "application/feed+json",
];

/** Common feed paths to probe as fallback when no links found. */
const COMMON_FEED_PATHS = [
  "/feed",
  "/feed/",
  "/rss",
  "/rss/",
  "/rss.xml",
  "/atom.xml",
  "/feed.xml",
  "/index.xml",
  "/feeds/posts/default",
  "/?feed=rss2",
];

/**
 * Detects feed type from content type header or URL patterns.
 *
 * @param contentType - HTTP Content-Type header value
 * @param url - Optional URL to check for type hints
 * @returns Detected feed type
 */
function detectFeedType(
  contentType: string,
  url?: string,
): "rss" | "atom" | "unknown" {
  const ct = contentType.toLowerCase();
  if (ct.includes("atom")) return "atom";
  if (ct.includes("rss")) return "rss";

  // Try to detect from URL pattern
  if (url) {
    const urlLower = url.toLowerCase();
    if (urlLower.includes("atom")) return "atom";
    if (urlLower.includes("rss")) return "rss";
  }

  if (ct.includes("xml")) return "unknown";
  return "unknown";
}

/**
 * Extracts text content from a title element, handling CDATA sections.
 *
 * @param titleContent - Raw title content from XML
 * @returns Clean title text
 */
function extractTitleText(titleContent: string): string {
  // Check for CDATA section
  const cdataMatch = titleContent.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  if (cdataMatch) {
    return cdataMatch[1].trim();
  }
  return titleContent.trim();
}

/**
 * Extracts feed title from XML content.
 *
 * @param xml - Raw XML content of the feed
 * @returns Feed title or undefined if not found
 */
function extractFeedTitle(xml: string): string | undefined {
  // Try RSS <title> (direct child of <channel>)
  // Match title content that may contain CDATA or plain text
  const rssMatch = xml.match(
    /<channel[^>]*>[\s\S]*?<title[^>]*>([\s\S]*?)<\/title>/i,
  );
  if (rssMatch) {
    return extractTitleText(rssMatch[1]);
  }

  // Try Atom <title> (direct child of <feed>)
  const atomMatch = xml.match(
    /<feed[^>]*>[\s\S]*?<title[^>]*>([\s\S]*?)<\/title>/i,
  );
  if (atomMatch) {
    return extractTitleText(atomMatch[1]);
  }

  return undefined;
}

/** Result of checking if a URL is a feed. */
interface FeedCheckResult {
  isFeed: boolean;
  type: "rss" | "atom" | "unknown";
  title?: string;
}

/**
 * Checks if a URL is a direct feed by fetching and inspecting content.
 *
 * @param url - URL to check
 * @returns Result indicating if it's a feed with type and title
 */
async function checkIfFeed(url: string): Promise<FeedCheckResult> {
  try {
    const response = await fetch(url, {
      method: "HEAD",
      headers: {
        "User-Agent": "BuunCurator/1.0 (Feed Discovery)",
      },
      redirect: "follow",
    });

    const contentType = response.headers.get("content-type") || "";

    // Check if it's a feed content type
    const isFeed = FEED_CONTENT_TYPES.some((type) =>
      contentType.toLowerCase().includes(type.split("/")[1]),
    );

    if (isFeed) {
      // Fetch the feed content to extract title
      const getResponse = await fetch(url, {
        headers: {
          "User-Agent": "BuunCurator/1.0 (Feed Discovery)",
        },
        redirect: "follow",
      });
      const text = await getResponse.text();
      const title = extractFeedTitle(text);
      return { isFeed: true, type: detectFeedType(contentType, url), title };
    }

    // If HEAD doesn't give us enough info, do a GET and check content
    if (contentType.includes("text/html") || !contentType) {
      const getResponse = await fetch(url, {
        headers: {
          "User-Agent": "BuunCurator/1.0 (Feed Discovery)",
        },
        redirect: "follow",
      });

      const text = await getResponse.text();
      const trimmed = text.trim();

      // Check for RSS
      if (trimmed.includes("<rss") || trimmed.includes("<rdf:RDF")) {
        const title = extractFeedTitle(trimmed);
        return { isFeed: true, type: "rss", title };
      }

      // Check for Atom
      if (trimmed.includes("<feed") && trimmed.includes("xmlns")) {
        const title = extractFeedTitle(trimmed);
        return { isFeed: true, type: "atom", title };
      }
    }

    return { isFeed: false, type: "unknown" };
  } catch {
    return { isFeed: false, type: "unknown" };
  }
}

/**
 * Extracts feed links from HTML document's link tags.
 *
 * @param html - HTML content to parse
 * @param baseUrl - Base URL for resolving relative links
 * @returns Discovered feeds and site title
 */
function extractFeedLinks(
  html: string,
  baseUrl: string,
): { feeds: DiscoveredFeed[]; siteTitle?: string } {
  const { document } = parseHTML(html);

  // Get site title
  const siteTitle =
    document.querySelector("title")?.textContent?.trim() || undefined;

  const feeds: DiscoveredFeed[] = [];
  const seenUrls = new Set<string>();

  // Find <link rel="alternate"> tags with feed types
  const linkElements = document.querySelectorAll(
    'link[rel="alternate"], link[rel="feed"]',
  );

  for (const link of linkElements) {
    const type = link.getAttribute("type") || "";
    const href = link.getAttribute("href");
    const title = link.getAttribute("title") || undefined;

    if (!href) continue;

    // Check if it's a feed type
    const isFeedType =
      FEED_LINK_TYPES.some((feedType) =>
        type.toLowerCase().includes(feedType.split("/")[1]),
      ) || link.getAttribute("rel") === "feed";

    if (isFeedType) {
      try {
        const absoluteUrl = new URL(href, baseUrl).toString();
        if (!seenUrls.has(absoluteUrl)) {
          seenUrls.add(absoluteUrl);
          feeds.push({
            url: absoluteUrl,
            title,
            type: detectFeedType(type, absoluteUrl),
          });
        }
      } catch {
        // Invalid URL, skip
      }
    }
  }

  return { feeds, siteTitle };
}

/**
 * Generates Medium-specific feed URL from a profile or publication URL.
 *
 * Medium feed URL patterns:
 * - User profile: https://medium.com/@username → https://medium.com/feed/@username
 * - Publication: https://medium.com/publication → https://medium.com/feed/publication
 *
 * @param url - Medium URL to convert
 * @returns Feed URL if applicable, null otherwise
 */
function getMediumFeedUrl(url: string): string | null {
  try {
    const parsed = new URL(url);
    if (parsed.hostname !== "medium.com") return null;

    // Remove trailing slash for consistent matching
    const pathname = parsed.pathname.replace(/\/$/, "");

    // Skip if already a feed URL
    if (pathname.startsWith("/feed")) return null;

    // Skip root path
    if (!pathname || pathname === "/") return null;

    // Convert to feed URL: /feed + pathname
    return `https://medium.com/feed${pathname}`;
  } catch {
    return null;
  }
}

/**
 * Probes common feed paths as fallback when no links found.
 *
 * @param baseUrl - Base URL to probe paths from
 * @returns List of discovered feeds from common paths
 */
async function tryCommonPaths(baseUrl: string): Promise<DiscoveredFeed[]> {
  const feeds: DiscoveredFeed[] = [];
  const origin = new URL(baseUrl).origin;

  // Try common paths in parallel (limit concurrency)
  const results = await Promise.allSettled(
    COMMON_FEED_PATHS.map(async (path) => {
      const url = new URL(path, origin).toString();
      const result = await checkIfFeed(url);
      if (result.isFeed) {
        return { url, type: result.type };
      }
      return null;
    }),
  );

  for (const result of results) {
    if (result.status === "fulfilled" && result.value) {
      // If type is unknown, try to detect from URL
      const feedType =
        result.value.type === "unknown"
          ? detectFeedType("", result.value.url)
          : result.value.type;
      feeds.push({
        url: result.value.url,
        type: feedType,
      });
    }
  }

  return feeds;
}

/**
 * Discovers feeds from a URL using multiple strategies.
 *
 * Discovery order:
 * 1. Check if URL is a direct feed
 * 2. Parse HTML and extract feed links from `<link>` tags
 * 3. Probe common feed paths as fallback
 *
 * @param url - URL to discover feeds from (with or without protocol)
 * @returns Discovery result with feeds and site metadata
 */
export async function discoverFeeds(url: string): Promise<FeedDiscoveryResult> {
  // Normalize URL
  let normalizedUrl = url.trim();
  if (
    !normalizedUrl.startsWith("http://") &&
    !normalizedUrl.startsWith("https://")
  ) {
    normalizedUrl = "https://" + normalizedUrl;
  }

  const parsedUrl = new URL(normalizedUrl);
  const siteUrl = parsedUrl.origin;

  // First, check if the URL itself is a feed
  const directCheck = await checkIfFeed(normalizedUrl);
  if (directCheck.isFeed) {
    return {
      feeds: [
        {
          url: normalizedUrl,
          title: directCheck.title,
          type: directCheck.type,
        },
      ],
      siteTitle: directCheck.title,
      siteUrl,
    };
  }

  // Try Medium-specific feed URL before fetching HTML
  const mediumFeedUrl = getMediumFeedUrl(normalizedUrl);
  if (mediumFeedUrl) {
    const mediumCheck = await checkIfFeed(mediumFeedUrl);
    if (mediumCheck.isFeed) {
      return {
        feeds: [
          {
            url: mediumFeedUrl,
            title: mediumCheck.title,
            type: mediumCheck.type,
          },
        ],
        siteTitle: mediumCheck.title,
        siteUrl,
      };
    }
  }

  // Fetch the page and look for feed links
  try {
    const response = await fetch(normalizedUrl, {
      headers: {
        "User-Agent": "BuunCurator/1.0 (Feed Discovery)",
        Accept: "text/html,application/xhtml+xml",
      },
      redirect: "follow",
    });

    if (!response.ok) {
      return {
        feeds: [],
        siteUrl,
        httpError: {
          status: response.status,
          statusText: response.statusText,
        },
      };
    }

    const html = await response.text();
    const { feeds, siteTitle } = extractFeedLinks(html, normalizedUrl);

    if (feeds.length > 0) {
      return {
        feeds,
        siteTitle,
        siteUrl,
      };
    }

    // Fallback: try common feed paths
    const commonFeeds = await tryCommonPaths(normalizedUrl);
    if (commonFeeds.length > 0) {
      return {
        feeds: commonFeeds,
        siteTitle,
        siteUrl,
      };
    }

    // No feeds found
    return {
      feeds: [],
      siteTitle,
      siteUrl,
    };
  } catch (error) {
    log.error({ error, siteUrl }, "feed discovery error");
    return {
      feeds: [],
      siteUrl,
    };
  }
}
