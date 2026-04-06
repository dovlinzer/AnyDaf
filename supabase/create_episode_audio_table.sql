-- Run once in the Supabase SQL editor (Database → SQL Editor → New query)
-- before running sync_episodes.py.

create table if not exists episode_audio (
  tractate    text         not null,
  daf         int          not null,
  audio_url   text         not null,  -- direct MP3 or "soundcloud-track://ID"
  updated_at  timestamptz  not null default now(),
  primary key (tractate, daf)
);

-- Reuse the update_updated_at() function from create_shiur_content_table.sql
create trigger episode_audio_updated_at
  before update on episode_audio
  for each row execute function update_updated_at();

-- Allow the app (anon role) to read but not write
alter table episode_audio enable row level security;

create policy "Public read access"
  on episode_audio for select
  using (true);
