CREATE TABLE "app_settings" (
	"id" char(26) PRIMARY KEY NOT NULL,
	"target_language" text,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);