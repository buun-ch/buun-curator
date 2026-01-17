CREATE TABLE "entry_links" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"entry_id" char(26) NOT NULL,
	"url" text NOT NULL,
	"title" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "entry_links" ADD CONSTRAINT "entry_links_entry_id_entries_id_fk" FOREIGN KEY ("entry_id") REFERENCES "public"."entries"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "entry_links_entry_id_idx" ON "entry_links" USING btree ("entry_id");--> statement-breakpoint
CREATE UNIQUE INDEX "entry_links_entry_url_title_idx" ON "entry_links" USING btree ("entry_id","url","title");