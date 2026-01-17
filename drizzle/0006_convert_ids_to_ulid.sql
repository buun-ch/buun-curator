-- Migration: Convert integer IDs to ULID (char(26))
-- WARNING: This migration will delete all existing data due to incompatible ID types

-- Drop foreign key constraints first
ALTER TABLE "entries" DROP CONSTRAINT IF EXISTS "entries_feed_id_feeds_id_fk";--> statement-breakpoint
ALTER TABLE "feeds" DROP CONSTRAINT IF EXISTS "feeds_category_id_categories_id_fk";--> statement-breakpoint

-- Drop the unique index on entries
DROP INDEX IF EXISTS "entries_url_idx";--> statement-breakpoint

-- Truncate tables (existing data cannot be migrated - integer to ULID)
TRUNCATE TABLE "entries" CASCADE;--> statement-breakpoint
TRUNCATE TABLE "feeds" CASCADE;--> statement-breakpoint
TRUNCATE TABLE "categories" CASCADE;--> statement-breakpoint

-- Drop default values that use serial sequences
ALTER TABLE "categories" ALTER COLUMN "id" DROP DEFAULT;--> statement-breakpoint
ALTER TABLE "feeds" ALTER COLUMN "id" DROP DEFAULT;--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "id" DROP DEFAULT;--> statement-breakpoint

-- Change column types to char(26) for ULID
ALTER TABLE "categories" ALTER COLUMN "id" SET DATA TYPE char(26);--> statement-breakpoint
ALTER TABLE "feeds" ALTER COLUMN "id" SET DATA TYPE char(26);--> statement-breakpoint
ALTER TABLE "feeds" ALTER COLUMN "category_id" SET DATA TYPE char(26);--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "id" SET DATA TYPE char(26);--> statement-breakpoint
ALTER TABLE "entries" ALTER COLUMN "feed_id" SET DATA TYPE char(26);--> statement-breakpoint

-- Recreate foreign key constraints
ALTER TABLE "feeds" ADD CONSTRAINT "feeds_category_id_categories_id_fk"
  FOREIGN KEY ("category_id") REFERENCES "categories"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;--> statement-breakpoint
ALTER TABLE "entries" ADD CONSTRAINT "entries_feed_id_feeds_id_fk"
  FOREIGN KEY ("feed_id") REFERENCES "feeds"("id") ON DELETE NO ACTION ON UPDATE NO ACTION;--> statement-breakpoint

-- Recreate unique index
CREATE UNIQUE INDEX "entries_url_idx" ON "entries" ("url");
