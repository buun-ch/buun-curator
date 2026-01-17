ALTER TABLE "entries" ADD COLUMN "context" json;--> statement-breakpoint
ALTER TABLE "entries" ADD COLUMN "context_saved_at" timestamp with time zone;--> statement-breakpoint
ALTER TABLE "entries" ADD COLUMN "keep_context" boolean DEFAULT false NOT NULL;