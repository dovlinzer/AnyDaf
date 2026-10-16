-- Separate flag for the Illustrated Talmud website (AnyDafWeb), so a dedication can target it
-- independently of the AnyDaf phone apps. Run manually in the Supabase SQL editor
-- (project zewdazoijdpakugfvnzt). Backfills from for_anydaf so current dedications keep showing.
ALTER TABLE dedications ADD COLUMN IF NOT EXISTS for_anydaf_web boolean NOT NULL DEFAULT false;
UPDATE dedications SET for_anydaf_web = for_anydaf;
