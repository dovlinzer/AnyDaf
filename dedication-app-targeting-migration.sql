-- AnyDaf / AnyTorah / AnyTorah Web Dedications — App Targeting Migration
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
--
-- Replaces the single `app` text column ('anydaf' | 'anytorah' | 'both') with three
-- independent boolean flags, so AnyTorah (native iOS/Android) and AnyTorah Web can be
-- targeted separately instead of AnyTorah Web silently riding along on whatever
-- `app` was set to. Safe to run more than once.

-- ── 1. Add the new columns ─────────────────────────────────────────────────
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS for_anydaf        boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS for_anytorah      boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS for_anytorah_web  boolean NOT NULL DEFAULT false;

-- ── 2. Backfill from the old `app` column ──────────────────────────────────
-- for_anytorah_web is intentionally left false for every existing row — nothing was
-- ever consciously tagged for the web app before this migration, so this doesn't
-- guess. Re-check "for_anytorah_web" on any still-relevant dedication (e.g. a
-- 'week'/'month' one) if you want it to also show on AnyTorah Web.
UPDATE dedications SET
  for_anydaf   = (app IN ('anydaf', 'both')),
  for_anytorah = (app IN ('anytorah', 'both'))
WHERE app IS NOT NULL;

-- ── 3. Old column is now unused ─────────────────────────────────────────────
-- The admin form no longer writes `app`. Left in place (not dropped) in case
-- anything else still reads it — drop it yourself once you've confirmed
-- everything works end to end:
--   ALTER TABLE dedications DROP COLUMN app;
ALTER TABLE dedications ALTER COLUMN app DROP NOT NULL;
ALTER TABLE dedications ALTER COLUMN app DROP DEFAULT;

-- No RLS policy changes needed — the existing policies key off `status`, not `app`.
