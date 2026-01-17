CREATE TABLE "articles" (
	"id" serial PRIMARY KEY NOT NULL,
	"feed_id" integer NOT NULL,
	"title" text NOT NULL,
	"url" text NOT NULL,
	"content" text,
	"summary" text,
	"author" text,
	"published_at" timestamp with time zone,
	"is_read" boolean DEFAULT false NOT NULL,
	"is_starred" boolean DEFAULT false NOT NULL,
	"metadata" json,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "articles" ADD CONSTRAINT "articles_feed_id_feeds_id_fk" FOREIGN KEY ("feed_id") REFERENCES "public"."feeds"("id") ON DELETE no action ON UPDATE no action;