-- Migration: change daf column from int to numeric(4,1) in shiur_content and shiur_sections.
--
-- Encoding convention (matches episode_audio):
--   N.0  = amud aleph (a-side) or whole-daf shiur
--   N.5  = amud bet  (b-side) shiur
--
-- Run once in the Supabase SQL editor (Database → SQL Editor → New query).

ALTER TABLE shiur_content  ALTER COLUMN daf TYPE numeric(4,1);
ALTER TABLE shiur_sections ALTER COLUMN daf TYPE numeric(4,1);
