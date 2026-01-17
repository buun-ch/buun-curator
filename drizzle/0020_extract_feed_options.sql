-- Add new columns with defaults
ALTER TABLE "feeds" ADD COLUMN "fetch_content" boolean DEFAULT true NOT NULL;
ALTER TABLE "feeds" ADD COLUMN "fetch_limit" integer DEFAULT 20 NOT NULL;

-- Migrate data from options JSON to new columns
UPDATE "feeds"
SET
  "fetch_content" = COALESCE((options->>'fetchContent')::boolean, true),
  "fetch_limit" = COALESCE((options->>'fetchLimit')::integer, 20)
WHERE options IS NOT NULL;

-- Remove fetchContent and fetchLimit from options JSON (keep extractionRules)
-- Cast to jsonb for the - operator, then back to json
UPDATE "feeds"
SET options = (options::jsonb - 'fetchContent' - 'fetchLimit')::json
WHERE options IS NOT NULL;

-- Set options to NULL if empty object
UPDATE "feeds"
SET options = NULL
WHERE options::jsonb = '{}'::jsonb;
