ALTER TABLE "entries" DROP CONSTRAINT "entries_feed_id_feeds_id_fk";
--> statement-breakpoint
ALTER TABLE "feeds" DROP CONSTRAINT "feeds_category_id_categories_id_fk";
--> statement-breakpoint
ALTER TABLE "entries" ADD COLUMN "preference" text;--> statement-breakpoint
ALTER TABLE "entries" ADD CONSTRAINT "entries_feed_id_feeds_id_fk" FOREIGN KEY ("feed_id") REFERENCES "public"."feeds"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "feeds" ADD CONSTRAINT "feeds_category_id_categories_id_fk" FOREIGN KEY ("category_id") REFERENCES "public"."categories"("id") ON DELETE set null ON UPDATE no action;