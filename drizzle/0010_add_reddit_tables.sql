CREATE TABLE "reddit_posts" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"post_id" text NOT NULL,
	"subreddit" text NOT NULL,
	"is_starred" boolean DEFAULT false NOT NULL,
	"is_read" boolean DEFAULT false NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "reddit_subreddits" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"min_score" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX "reddit_posts_post_id_idx" ON "reddit_posts" USING btree ("post_id");--> statement-breakpoint
CREATE UNIQUE INDEX "reddit_subreddits_name_idx" ON "reddit_subreddits" USING btree ("name");