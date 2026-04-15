-- Run this once in the Supabase SQL editor after create_shiur_content_table.sql.

create table if not exists shiur_sections (
  id                    bigint generated always as identity primary key,
  tractate              text    not null,
  -- numeric(4,1): N.0 = amud aleph / whole-daf, N.5 = amud bet
  daf                   numeric(4,1) not null,
  segment_index         int     not null,   -- globally sequential within the daf (macro + micro)
  parent_segment_index  int,               -- null = macro segment; int = micro (points to parent macro's segment_index)
  title                 text    not null,   -- segment title (macro ≤25 chars; micro may be longer)
  timestamp_mm_ss       text,               -- "MM:SS" — human-readable
  timestamp_secs        float,              -- seconds — for seek() in the audio player
  content               text,               -- written prose for this segment (from rewrite)

  updated_at            timestamptz not null default now(),

  unique (tractate, daf, segment_index)
);

-- Migration: add parent_segment_index to an existing table.
alter table shiur_sections
  add column if not exists parent_segment_index integer;

-- Full-text search vector, auto-updated by trigger below.
-- Weights: title (A = highest), content (B).
alter table shiur_sections
  add column if not exists content_search tsvector
    generated always as (
      setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
      setweight(to_tsvector('english', coalesce(content, '')), 'B')
    ) stored;

-- GIN index makes full-text search fast even over thousands of sections.
create index if not exists shiur_sections_search_idx
  on shiur_sections using gin(content_search);

-- Index for the most common app lookup: all sections for a given daf.
create index if not exists shiur_sections_tractate_daf_idx
  on shiur_sections (tractate, daf, segment_index);

-- Auto-update updated_at
create trigger shiur_sections_updated_at
  before update on shiur_sections
  for each row execute function update_updated_at();  -- reuses function from shiur_content

-- Row-level security: public read, service-role writes.
alter table shiur_sections enable row level security;

create policy "Public read access"
  on shiur_sections for select
  using (true);
