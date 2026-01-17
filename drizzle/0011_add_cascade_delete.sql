-- Drop existing foreign key constraints
ALTER TABLE "entries" DROP CONSTRAINT IF EXISTS "entries_feed_id_feeds_id_fk";
ALTER TABLE "feeds" DROP CONSTRAINT IF EXISTS "feeds_category_id_categories_id_fk";

-- Re-add with cascade/set null options
ALTER TABLE "entries" ADD CONSTRAINT "entries_feed_id_feeds_id_fk"
  FOREIGN KEY ("feed_id") REFERENCES "feeds"("id") ON DELETE CASCADE;

ALTER TABLE "feeds" ADD CONSTRAINT "feeds_category_id_categories_id_fk"
  FOREIGN KEY ("category_id") REFERENCES "categories"("id") ON DELETE SET NULL;
