-- Saved copy of the Bavli text (Hebrew/Aramaic + Sefaria's English), one row per amud.
-- Loaded by daf-processor/build_daf_text.py --upload. Run once in the Supabase SQL editor.
-- Segment numbers (n) are Sefaria's own 1-based positions in the amud, the numbering the study
-- outline's anchors use ("6a.8" = amud 6a, n = 8). Text keeps Sefaria's **bold** markup.
-- English: The William Davidson Talmud (Sefaria), CC BY-NC — pages showing it need a credit line.

create table if not exists daf_text (
  tractate   text not null,            -- Sefaria spelling (Eiruvin, Taanit, Hullin, ...)
  amud       text not null,            -- '6a', '6b'
  daf        integer not null,
  side       char(1) not null check (side in ('a', 'b')),
  segments   jsonb not null,           -- [{"n": 1, "he": "...", "en": "..."}]
  source     text not null default 'cache',   -- cache (pipeline files) | sefaria (fetched)
  updated_at timestamptz default now(),
  primary key (tractate, amud)
);
create index if not exists daf_text_tractate_daf on daf_text (tractate, daf);

-- Public text: anyone may read; only the service role writes.
alter table daf_text enable row level security;
drop policy if exists "daf_text is readable" on daf_text;
create policy "daf_text is readable" on daf_text for select using (true);
