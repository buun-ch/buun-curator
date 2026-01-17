ALTER TABLE "entries" ADD COLUMN "thumbnail_url" text;--> statement-breakpoint

UPDATE "entries"
SET "thumbnail_url" = metadata->>'thumbnailUrl'
WHERE metadata->>'thumbnailUrl' IS NOT NULL;
