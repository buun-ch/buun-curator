ALTER TABLE "entries" RENAME COLUMN "content" TO "feed_content";--> statement-breakpoint
UPDATE "entries" SET "feed_content" = '' WHERE "feed_content" IS NULL;--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "feed_content" SET DEFAULT '';--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "feed_content" SET NOT NULL;--> statement-breakpoint
UPDATE "entries" SET "summary" = '' WHERE "summary" IS NULL;--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "summary" SET DEFAULT '';--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "summary" SET NOT NULL;--> statement-breakpoint
ALTER TABLE "entries" ADD COLUMN "full_content" text DEFAULT '' NOT NULL;