import { NextResponse } from "next/server";

import { checkRedditEnabled } from "@/lib/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:reddit:subreddit:posts");

const REDDIT_BASE_URL = "https://www.reddit.com";

interface RedditPostData {
  id: string;
  title: string;
  subreddit: string;
  author: string;
  score: number;
  num_comments: number;
  created_utc: number;
  url: string;
  permalink: string;
  selftext?: string;
  thumbnail?: string;
  over_18: boolean;
}

interface RedditListingResponse {
  data: {
    children: Array<{ data: RedditPostData }>;
    after?: string;
  };
}

function cleanThumbnail(thumbnail: string | undefined): string | undefined {
  if (!thumbnail) return undefined;
  if (
    thumbnail === "" ||
    thumbnail === "default" ||
    thumbnail === "self" ||
    thumbnail === "nsfw" ||
    thumbnail === "spoiler"
  ) {
    return undefined;
  }
  return thumbnail.replace(/&amp;/g, "&");
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ name: string }> },
) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  const { name: subredditName } = await params;
  const { searchParams } = new URL(request.url);

  const sort = searchParams.get("sort") || "hot";
  const limit = Math.min(parseInt(searchParams.get("limit") || "25", 10), 100);
  const after = searchParams.get("after") || "";
  const time = searchParams.get("time") || "day"; // for "top" sort

  try {
    let url = `${REDDIT_BASE_URL}/r/${subredditName}/${sort}.json?limit=${limit}`;
    if (after) {
      url += `&after=${after}`;
    }
    if (sort === "top" || sort === "controversial") {
      url += `&t=${time}`;
    }

    const response = await fetch(url, {
      headers: {
        "User-Agent": "BuunCurator/1.0",
      },
      next: {
        revalidate: 60, // Cache for 1 minute
      },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Failed to fetch posts: ${response.status}` },
        { status: response.status },
      );
    }

    const json: RedditListingResponse = await response.json();

    const posts = json.data.children.map(({ data }) => ({
      id: data.id,
      title: data.title,
      subreddit: data.subreddit,
      author: data.author,
      score: data.score,
      numComments: data.num_comments,
      createdAt: new Date(data.created_utc * 1000).toISOString(),
      url: data.url,
      permalink: data.permalink,
      selftext: data.selftext || undefined,
      thumbnail: cleanThumbnail(data.thumbnail),
      isNsfw: data.over_18,
    }));

    return NextResponse.json({
      posts,
      after: json.data.after || null,
    });
  } catch (error) {
    log.error({ error }, "Failed to fetch posts");
    return NextResponse.json(
      { error: "Failed to fetch posts" },
      { status: 500 },
    );
  }
}
