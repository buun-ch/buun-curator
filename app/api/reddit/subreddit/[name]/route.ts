import { NextResponse } from "next/server";

import { checkRedditEnabled } from "@/lib/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:reddit:subreddit");

const REDDIT_BASE_URL = "https://www.reddit.com";

interface RedditSubredditResponse {
  data: {
    display_name: string;
    title: string;
    public_description: string;
    description: string;
    subscribers: number;
    accounts_active?: number;
    created_utc: number;
    over18: boolean;
    icon_img?: string;
    banner_background_image?: string;
    community_icon?: string;
  };
}

function cleanImageUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  const cleaned = url.replace(/&amp;/g, "&");
  if (cleaned === "" || cleaned === "default" || cleaned === "self") {
    return undefined;
  }
  return cleaned;
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ");
}

function cleanDescription(text: string | undefined): string | undefined {
  if (!text) return undefined;
  // Decode HTML entities
  let cleaned = decodeHtmlEntities(text);
  // Remove markdown-style comments like [](#icon-xxx)
  cleaned = cleaned.replace(/\[.*?\]\(#[^)]*\)/g, "");
  // Remove markdown headers (##### Header)
  cleaned = cleaned.replace(/^#{1,6}\s+/gm, "");
  // Remove markdown bold/italic (*text*, **text**, _text_, __text__)
  cleaned = cleaned.replace(/(\*\*|__)(.*?)\1/g, "$2");
  cleaned = cleaned.replace(/(\*|_)(.*?)\1/g, "$2");
  // Remove markdown links [text](url) -> text
  cleaned = cleaned.replace(/\[([^\]]*)\]\([^)]*\)/g, "$1");
  // Remove markdown blockquotes (> )
  cleaned = cleaned.replace(/^>\s*/gm, "");
  // Remove horizontal rules (---, ***, ___)
  cleaned = cleaned.replace(/^[-*_]{3,}\s*$/gm, "");
  // Remove multiple consecutive newlines
  cleaned = cleaned.replace(/\n{3,}/g, "\n\n");
  // Trim whitespace from each line and overall
  cleaned = cleaned
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    .trim();
  return cleaned || undefined;
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> }
) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  const { name: subredditName } = await params;

  try {
    const response = await fetch(
      `${REDDIT_BASE_URL}/r/${subredditName}/about.json`,
      {
        headers: {
          "User-Agent": "BuunCurator/1.0",
        },
        next: {
          revalidate: 300, // Cache for 5 minutes
        },
      }
    );

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch subreddit: ${response.status}` },
        { status: response.status }
      );
    }

    const json: RedditSubredditResponse = await response.json();
    const data = json.data;

    const subredditInfo = {
      name: data.display_name.toLowerCase(),
      displayName: data.display_name,
      title: data.title,
      description: cleanDescription(data.public_description || data.description),
      subscribers: data.subscribers,
      activeUsers: data.accounts_active,
      createdAt: new Date(data.created_utc * 1000).toISOString(),
      isNsfw: data.over18,
      iconUrl: cleanImageUrl(data.community_icon || data.icon_img),
      bannerUrl: cleanImageUrl(data.banner_background_image),
    };

    return NextResponse.json(subredditInfo);
  } catch (error) {
    log.error({ error }, "Failed to fetch subreddit");
    return NextResponse.json(
      { error: "Failed to fetch subreddit" },
      { status: 500 }
    );
  }
}
