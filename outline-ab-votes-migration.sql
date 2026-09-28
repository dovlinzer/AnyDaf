-- Votes from the blind A/B outline test (Medium vs High effort). Run once in the Supabase SQL editor.
-- The test site uses the public anon key and may only INSERT. A tester who changes a vote adds a
-- new row; the latest row per (tester_id, daf) counts. Which version is A on each daf is kept only
-- in daf-processor/outline/ab_key_<round>.json, never in this table or the page.

create table if not exists public.outline_ab_votes (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),
  round         text not null,          -- e.g. 'round3' (names the key file used to unblind)
  tester_id     text not null,          -- random id kept in the tester's browser, groups one tester's votes
  tester_name   text,
  tester_email  text,
  daf           text not null,          -- daf key, e.g. 'kiddushin_3'
  overall       text,                   -- 'A' / 'B' / 'same'
  structure     text,
  charts        text,
  pictures      text,
  note          text,
  constraint outline_ab_votes_values check (
    coalesce(overall, 'A') in ('A', 'B', 'same') and coalesce(structure, 'A') in ('A', 'B', 'same')
    and coalesce(charts, 'A') in ('A', 'B', 'same') and coalesce(pictures, 'A') in ('A', 'B', 'same')),
  constraint outline_ab_votes_sizes check (
    char_length(round) <= 32 and char_length(tester_id) <= 64 and char_length(daf) <= 64
    and char_length(coalesce(tester_name, '')) <= 120 and char_length(coalesce(tester_email, '')) <= 200
    and char_length(coalesce(note, '')) <= 4000)
);

alter table public.outline_ab_votes enable row level security;

drop policy if exists "testers add votes" on public.outline_ab_votes;
create policy "testers add votes" on public.outline_ab_votes
  for insert to anon, authenticated
  with check (true);

-- No select / update / delete policies: testers can't see or change anyone's votes.
grant insert on public.outline_ab_votes to anon, authenticated;
revoke select, update, delete on public.outline_ab_votes from anon, authenticated;

create index if not exists outline_ab_votes_daf on public.outline_ab_votes (round, daf);
