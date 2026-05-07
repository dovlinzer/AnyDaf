-- AskAnyDaf: shiur_sections table (updated schema with talmudic_text, source_type, embedding)
-- Run this in Supabase SQL Editor after upgrading to Pro.
--
-- Enable pgvector extension first (if not already enabled):
--   CREATE EXTENSION IF NOT EXISTS vector;
--
-- If the table already exists from the old schema, drop and recreate:
--   DROP TABLE IF EXISTS shiur_sections;

CREATE TABLE IF NOT EXISTS shiur_sections (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tractate             text NOT NULL,
  daf                  numeric(4,1) NOT NULL,   -- N.0 = amud aleph, N.5 = amud bet
  segment_index        integer NOT NULL,
  parent_segment_index integer,                 -- null = macro; int = micro (index of parent macro)
  title                text,
  timestamp_mm_ss      text,                    -- "MM:SS" human-readable
  timestamp_secs       numeric,                 -- seconds, for audio seek
  content              text,                    -- shiur lecture text
  talmudic_text        text,                    -- Hebrew/Aramaic + English translation blockquote
  source_type          text NOT NULL DEFAULT 'talmudic',
                                                -- 'talmudic' | 'mishnah' | 'shiur_discussion'
  embedding            vector(512),             -- text-embedding-3-small at 512 dims
  updated_at           timestamptz DEFAULT now(),

  UNIQUE (tractate, daf, segment_index)
);

-- Fast lookup by tractate/daf
CREATE INDEX IF NOT EXISTS shiur_sections_tractate_daf_idx
  ON shiur_sections (tractate, daf, segment_index);

-- Full-text search (title weighted higher than content)
ALTER TABLE shiur_sections
  ADD COLUMN IF NOT EXISTS content_search tsvector
    GENERATED ALWAYS AS (
      setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
      setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) STORED;

CREATE INDEX IF NOT EXISTS shiur_sections_search_idx
  ON shiur_sections USING gin (content_search);

-- Cosine similarity vector search.
-- Create AFTER bulk load completes (not before), so index builds on real data.
-- Tune lists= based on row count: ~sqrt(row_count) is a good starting point.
-- CREATE INDEX shiur_sections_embedding_idx
--   ON shiur_sections USING ivfflat (embedding vector_cosine_ops) WITH (lists = 320);

-- Row-level security: anon read, service-role writes
ALTER TABLE shiur_sections ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read access"
  ON shiur_sections FOR SELECT
  USING (true);

-- After bulk load:
-- ANALYZE shiur_sections;
-- Then create the ivfflat index above.
