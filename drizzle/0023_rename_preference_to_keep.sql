-- Rename preference column to keep (boolean)
-- Convert preference='up' to keep=true, all others to keep=false

-- Add keep column with default false
ALTER TABLE "entries" ADD COLUMN "keep" boolean DEFAULT false NOT NULL;

-- Migrate data: preference='up' -> keep=true
UPDATE "entries" SET "keep" = true WHERE "preference" = 'up';

-- Drop preference column
ALTER TABLE "entries" DROP COLUMN "preference";
