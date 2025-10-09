-- ================================================
-- Changeset 012: Add Embedding Column to kb_chunk
-- Description: Adds embedding column for storing vector embeddings as JSON
-- Table: kb_chunk
-- ================================================

-- alter table section -------------------------------------------------

-- Add embedding column to kb_chunk table
ALTER TABLE kb_chunk ADD COLUMN IF NOT EXISTS embedding TEXT;

-- create comments section -------------------------------------------------

COMMENT ON COLUMN kb_chunk.embedding IS 'JSON string containing vector embeddings for semantic search';