-- Run this once in the Supabase SQL editor (Database → SQL Editor → New query)
-- before using upload_to_supabase.py.

create table if not exists shiur_content (
  id            bigint generated always as identity primary key,
  tractate      text        not null,
  -- numeric(4,1): N.0 = amud aleph / whole-daf, N.5 = amud bet
  daf           numeric(4,1) not null,

  -- Pass 1 output: macro/micro segments and topical tags (stored as JSONB for querying)
  segmentation  jsonb,

  -- Pass 2 output: polished markdown essay (no source text interspersed)
  rewrite       text,

  -- Pass 3 output: markdown essay with Sefaria source passages inserted
  final         text,

  updated_at    timestamptz not null default now(),

  unique (tractate, daf)
);

-- Automatically update updated_at on any row change
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger shiur_content_updated_at
  before update on shiur_content
  for each row execute function update_updated_at();

-- Index for the most common app query pattern: lookup by tractate + daf
create index if not exists shiur_content_tractate_daf
  on shiur_content (tractate, daf);

-- Allow the app (anon/authenticated role) to read but not write
alter table shiur_content enable row level security;

create policy "Public read access"
  on shiur_content for select
  using (true);

-- The service-role key used by upload_to_supabase.py bypasses RLS entirely,
-- so no insert/update policy is needed for the uploader.
