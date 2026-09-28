-- Reader feedback on the study outlines (the AnyDaf outline preview site, and later the web app).
-- Run once in the Supabase SQL editor. The site uses the public anon key and may only INSERT:
-- it can't read, change or delete anyone's notes. Read them with the service key (Claude, via
-- daf-processor) or in the Supabase table editor.

create table if not exists public.outline_feedback (
  id            bigint generated always as identity primary key,
  created_at    timestamptz not null default now(),
  daf           text not null,          -- daf key, e.g. 'kiddushin_3'
  version       text,                   -- 'M' / 'H' for the effort test; null for a single version
  section_id    text,                   -- outline section id ('s4'); null for a note on the whole daf
  section_title text,
  kind          text not null,          -- heading, gist, structure, add_chart, fix_chart, add_picture,
                                        -- fix_picture, content, other
  note          text not null,
  reader_name   text,
  reader_email  text,                   -- optional, only if the reader wants a reply
  status        text not null default 'open',   -- open / applied / declined (set by us, not by readers)
  constraint outline_feedback_sizes check (
    char_length(daf) <= 64 and char_length(coalesce(version, '')) <= 8
    and char_length(coalesce(section_id, '')) <= 32 and char_length(coalesce(section_title, '')) <= 300
    and char_length(kind) <= 32 and char_length(note) between 1 and 4000
    and char_length(coalesce(reader_name, '')) <= 120 and char_length(coalesce(reader_email, '')) <= 200)
);

alter table public.outline_feedback enable row level security;

-- Anyone with the site may add a note, as long as it arrives as 'open'.
drop policy if exists "readers add notes" on public.outline_feedback;
create policy "readers add notes" on public.outline_feedback
  for insert to anon, authenticated
  with check (status = 'open');

-- No select / update / delete policies: readers can't see or touch other notes.
-- (The service role bypasses RLS, so Claude and the table editor can read and mark them.)
grant insert on public.outline_feedback to anon, authenticated;
revoke select, update, delete on public.outline_feedback from anon, authenticated;

create index if not exists outline_feedback_daf on public.outline_feedback (daf, version);
