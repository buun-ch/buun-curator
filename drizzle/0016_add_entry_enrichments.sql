CREATE TABLE "entry_enrichments" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"entry_id" char(26) NOT NULL,
	"type" text NOT NULL,
	"data" json,
	"source" text,
	"metadata" json,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"expires_at" timestamp with time zone
);
--> statement-breakpoint
ALTER TABLE "entry_enrichments" ADD CONSTRAINT "entry_enrichments_entry_id_entries_id_fk" FOREIGN KEY ("entry_id") REFERENCES "public"."entries"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "entry_enrichments_entry_id_idx" ON "entry_enrichments" USING btree ("entry_id");