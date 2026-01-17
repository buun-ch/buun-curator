CREATE TABLE "entry_labels" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"entry_id" char(26) NOT NULL,
	"label_id" char(26) NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "labels" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"name" text NOT NULL,
	"color" text NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
ALTER TABLE "entry_labels" ADD CONSTRAINT "entry_labels_entry_id_entries_id_fk" FOREIGN KEY ("entry_id") REFERENCES "public"."entries"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "entry_labels" ADD CONSTRAINT "entry_labels_label_id_labels_id_fk" FOREIGN KEY ("label_id") REFERENCES "public"."labels"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE INDEX "entry_labels_entry_id_idx" ON "entry_labels" USING btree ("entry_id");--> statement-breakpoint
CREATE INDEX "entry_labels_label_id_idx" ON "entry_labels" USING btree ("label_id");--> statement-breakpoint
CREATE UNIQUE INDEX "entry_labels_entry_label_idx" ON "entry_labels" USING btree ("entry_id","label_id");
