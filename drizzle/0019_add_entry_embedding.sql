-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column for recommendation scoring
ALTER TABLE "entries" ADD COLUMN "embedding" vector(768);
