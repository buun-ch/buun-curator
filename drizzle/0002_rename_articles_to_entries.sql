ALTER TABLE "articles" RENAME TO "entries";--> statement-breakpoint
ALTER TABLE "entries" DROP CONSTRAINT "articles_feed_id_feeds_id_fk";
--> statement-breakpoint
ALTER TABLE "entries" ADD CONSTRAINT "entries_feed_id_feeds_id_fk" FOREIGN KEY ("feed_id") REFERENCES "public"."feeds"("id") ON DELETE no action ON UPDATE no action;