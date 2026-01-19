/**
 * Reddit API client for fetching subreddit info and posts.
 *
 * Calls internal Next.js API routes which proxy to Reddit's public API
 * to avoid CORS issues in the browser.
 *
 * @module lib/reddit-api
 */

import type {
  SubredditInfo,
  RedditPost,
  RedditPostDetail,
  RedditComment,
} from "./types";

/** API response type from our internal endpoint (dates as ISO strings). */
interface SubredditInfoResponse {
  name: string;
  displayName: string;
  title: string;
  description: string;
  subscribers: number;
  activeUsers?: number;
  createdAt: string;
  isNsfw: boolean;
  iconUrl?: string;
  bannerUrl?: string;
}

/**
 * Fetches subreddit information via internal API.
 *
 * @param subredditName - Name of the subreddit (without r/ prefix)
 * @returns Subreddit metadata including subscribers, description, etc.
 * @throws Error if the subreddit is not found or request fails
 */
export async function fetchSubredditInfo(
  subredditName: string,
): Promise<SubredditInfo> {
  const response = await fetch(`/api/reddit/subreddit/${subredditName}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(
      error.error || `Failed to fetch subreddit: ${response.status}`,
    );
  }

  const data: SubredditInfoResponse = await response.json();

  return {
    ...data,
    createdAt: new Date(data.createdAt),
  };
}

/** API response type for posts (dates as ISO strings). */
interface RedditPostResponse {
  id: string;
  title: string;
  subreddit: string;
  author: string;
  score: number;
  numComments: number;
  createdAt: string;
  url: string;
  permalink: string;
  selftext?: string;
  thumbnail?: string;
  isNsfw: boolean;
}

/** Posts list API response with pagination cursor. */
interface PostsResponse {
  posts: RedditPostResponse[];
  after: string | null;
}

/** Post sort options for subreddit listing. */
export type PostSortOption = "hot" | "new" | "top" | "rising" | "controversial";

/** Time filter options for top/controversial sorting. */
export type TimeFilterOption =
  | "hour"
  | "day"
  | "week"
  | "month"
  | "year"
  | "all";

/**
 * Fetches posts from a subreddit with sorting and pagination.
 *
 * @param subredditName - Name of the subreddit (without r/ prefix)
 * @param options - Sort, time filter, limit, and pagination options
 * @returns Posts array and pagination cursor
 * @throws Error if the subreddit is not found or request fails
 */
export async function fetchSubredditPosts(
  subredditName: string,
  options: {
    sort?: PostSortOption;
    time?: TimeFilterOption;
    limit?: number;
    after?: string;
  } = {},
): Promise<{ posts: RedditPost[]; after: string | null }> {
  const { sort = "hot", time = "day", limit = 25, after } = options;

  const params = new URLSearchParams({
    sort,
    limit: limit.toString(),
  });
  if (after) {
    params.set("after", after);
  }
  if (sort === "top" || sort === "controversial") {
    params.set("time", time);
  }

  const response = await fetch(
    `/api/reddit/subreddit/${subredditName}/posts?${params}`,
  );

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Failed to fetch posts: ${response.status}`);
  }

  const data: PostsResponse = await response.json();

  return {
    posts: data.posts.map((post) => ({
      ...post,
      createdAt: new Date(post.createdAt),
    })),
    after: data.after,
  };
}

/** API response type for post detail (dates as ISO strings). */
interface RedditPostDetailResponse {
  id: string;
  title: string;
  subreddit: string;
  subredditPrefixed: string;
  author: string;
  score: number;
  upvoteRatio: number;
  numComments: number;
  createdAt: string;
  url: string;
  permalink: string;
  selftext?: string;
  selftextHtml?: string;
  thumbnail?: string;
  previewUrl?: string;
  isVideo: boolean;
  videoUrl?: string;
  isNsfw: boolean;
  flair?: string;
  domain: string;
  isSelf: boolean;
}

/** API response type for comments (dates as ISO strings). */
interface RedditCommentResponse {
  id: string;
  author: string;
  body: string;
  bodyHtml?: string;
  score: number;
  createdAt: string;
  depth: number;
  isSubmitter: boolean;
  stickied: boolean;
  replies: RedditCommentResponse[];
}

/** Full post detail response including comments. */
interface PostDetailResponse {
  post: RedditPostDetailResponse;
  comments: RedditCommentResponse[];
}

/** Transforms API comment response to domain type with Date objects. */
function transformComment(comment: RedditCommentResponse): RedditComment {
  return {
    ...comment,
    createdAt: new Date(comment.createdAt),
    replies: comment.replies.map(transformComment),
  };
}

/**
 * Fetches Reddit post details with comments via internal API.
 *
 * @param postId - Reddit post ID (e.g., "1abc2d3")
 * @param options - Comment sort, limit, and depth options
 * @returns Post detail and nested comment tree
 * @throws Error if the post is not found or request fails
 */
export async function fetchRedditPost(
  postId: string,
  options: {
    sort?: "best" | "top" | "new" | "controversial" | "old" | "qa";
    limit?: number;
    depth?: number;
  } = {},
): Promise<{ post: RedditPostDetail; comments: RedditComment[] }> {
  const { sort = "best", limit = 50, depth = 5 } = options;

  const params = new URLSearchParams({
    sort,
    limit: limit.toString(),
    depth: depth.toString(),
  });

  const response = await fetch(`/api/reddit/post/${postId}?${params}`);

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `Failed to fetch post: ${response.status}`);
  }

  const data: PostDetailResponse = await response.json();

  return {
    post: {
      ...data.post,
      createdAt: new Date(data.post.createdAt),
    },
    comments: data.comments.map(transformComment),
  };
}

/**
 * Searches Reddit posts across subreddits.
 *
 * @param _query - Search query string
 * @param _options - Search options (subreddit, sort, time, pagination)
 * @returns Posts array and pagination cursor
 * @throws Error - Not yet implemented
 *
 * @remarks
 * TODO: Create /api/reddit/search route to implement this
 */
export async function searchRedditPosts(
  _query: string,
  _options: {
    subreddit?: string;
    sort?: "relevance" | "hot" | "top" | "new" | "comments";
    time?: "hour" | "day" | "week" | "month" | "year" | "all";
    limit?: number;
    after?: string;
  } = {},
): Promise<{ posts: RedditPost[]; after?: string }> {
  // TODO: Implement via internal API route
  throw new Error("Not implemented");
}
