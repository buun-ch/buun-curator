import { NextResponse } from "next/server";

import { checkRedditEnabled } from "@/lib/config";
import { createLogger } from "@/lib/logger";

const log = createLogger("api:reddit:post");

const REDDIT_BASE_URL = "https://www.reddit.com";

interface RedditPostData {
  id: string;
  title: string;
  subreddit: string;
  subreddit_name_prefixed: string;
  author: string;
  score: number;
  upvote_ratio: number;
  num_comments: number;
  created_utc: number;
  url: string;
  permalink: string;
  selftext: string;
  selftext_html?: string;
  thumbnail?: string;
  preview?: {
    images: Array<{
      source: { url: string; width: number; height: number };
    }>;
  };
  is_video: boolean;
  media?: {
    reddit_video?: {
      fallback_url: string;
      width: number;
      height: number;
    };
  };
  over_18: boolean;
  link_flair_text?: string;
  domain: string;
  is_self: boolean;
}

interface RedditCommentData {
  id: string;
  author: string;
  body: string;
  body_html: string;
  score: number;
  created_utc: number;
  replies?: {
    data?: {
      children: Array<{ kind: string; data: RedditCommentData }>;
    };
  };
  depth: number;
  is_submitter: boolean;
  stickied: boolean;
}

interface RedditListingResponse {
  data: {
    children: Array<{ kind: string; data: RedditPostData | RedditCommentData }>;
  };
}

function cleanHtml(html: string | undefined): string | undefined {
  if (!html) return undefined;
  // Decode HTML entities
  return html
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

function cleanUrl(url: string | undefined): string | undefined {
  if (!url) return undefined;
  return url.replace(/&amp;/g, "&");
}

function transformComment(data: RedditCommentData, maxDepth: number): object | null {
  if (data.depth > maxDepth) return null;

  const replies: object[] = [];
  if (data.replies?.data?.children) {
    for (const child of data.replies.data.children) {
      if (child.kind === "t1") {
        const reply = transformComment(child.data as RedditCommentData, maxDepth);
        if (reply) replies.push(reply);
      }
    }
  }

  return {
    id: data.id,
    author: data.author,
    body: data.body,
    bodyHtml: cleanHtml(data.body_html),
    score: data.score,
    createdAt: new Date(data.created_utc * 1000).toISOString(),
    depth: data.depth,
    isSubmitter: data.is_submitter,
    stickied: data.stickied,
    replies,
  };
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const disabled = checkRedditEnabled();
  if (disabled) return disabled;

  const { id: postId } = await params;
  const { searchParams } = new URL(request.url);

  const commentSort = searchParams.get("sort") || "best";
  const commentLimit = Math.min(
    parseInt(searchParams.get("limit") || "50", 10),
    200
  );
  const commentDepth = Math.min(
    parseInt(searchParams.get("depth") || "5", 10),
    10
  );

  try {
    // Reddit API requires subreddit in URL, but we can use /comments/[id] directly
    const url = `${REDDIT_BASE_URL}/comments/${postId}.json?sort=${commentSort}&limit=${commentLimit}&depth=${commentDepth}`;

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
        { error: `Failed to fetch post: ${response.status}` },
        { status: response.status }
      );
    }

    const json: RedditListingResponse[] = await response.json();

    // First listing contains the post
    const postData = json[0].data.children[0].data as RedditPostData;

    // Second listing contains comments
    const comments: object[] = [];
    if (json[1]?.data?.children) {
      for (const child of json[1].data.children) {
        if (child.kind === "t1") {
          const comment = transformComment(
            child.data as RedditCommentData,
            commentDepth
          );
          if (comment) comments.push(comment);
        }
      }
    }

    // Get preview image if available
    let previewUrl: string | undefined;
    if (postData.preview?.images?.[0]?.source?.url) {
      previewUrl = cleanUrl(postData.preview.images[0].source.url);
    }

    const post = {
      id: postData.id,
      title: postData.title,
      subreddit: postData.subreddit,
      subredditPrefixed: postData.subreddit_name_prefixed,
      author: postData.author,
      score: postData.score,
      upvoteRatio: postData.upvote_ratio,
      numComments: postData.num_comments,
      createdAt: new Date(postData.created_utc * 1000).toISOString(),
      url: postData.url,
      permalink: postData.permalink,
      selftext: postData.selftext || undefined,
      selftextHtml: cleanHtml(postData.selftext_html),
      thumbnail: cleanUrl(postData.thumbnail),
      previewUrl,
      isVideo: postData.is_video,
      videoUrl: postData.media?.reddit_video?.fallback_url
        ? cleanUrl(postData.media.reddit_video.fallback_url)
        : undefined,
      isNsfw: postData.over_18,
      flair: postData.link_flair_text || undefined,
      domain: postData.domain,
      isSelf: postData.is_self,
    };

    return NextResponse.json({
      post,
      comments,
    });
  } catch (error) {
    log.error({ error }, "Failed to fetch post");
    return NextResponse.json(
      { error: "Failed to fetch post" },
      { status: 500 }
    );
  }
}
