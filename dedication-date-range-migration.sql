-- AnyDaf / AnyTorah / AnyTorah Web Dedications — Date Range Migration
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
--
-- Adds an explicit `end_date` column so a dedication can cover an arbitrary date range
-- (not just the fixed calendar week/month the `period` column used to imply via client-side
-- Calendar math). The apps' "is this active today" check becomes a plain
-- `date <= today <= end_date` comparison, done as a Supabase query filter — replacing the
-- calendar-week/calendar-month comparison logic that used to live in each client.
--
-- `period` is UNCHANGED in meaning for display purposes — it still drives only the banner
-- text ("Today's Learning" / "This Week's Learning" / "This Month's Learning"). It no longer
-- determines the actual active window; `date`/`end_date` do that now.
--
-- Safe to run more than once.

-- ── 1. Add the column, nullable for the backfill step ──────────────────────
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS end_date date;

-- ── 2. Backfill existing rows so their active window doesn't change ────────

-- 'today' (or any other/missing period): single day.
UPDATE dedications SET end_date = date
WHERE end_date IS NULL AND (period IS NULL OR period NOT IN ('week', 'month'));

-- 'week': matches the old Calendar.current weekOfYear comparison the apps used to run
-- (Sunday-start week, the US-locale default) — end of the calendar week containing `date`.
-- EXTRACT(DOW FROM date) is 0=Sunday..6=Saturday in Postgres, so 6-DOW is days until Saturday.
UPDATE dedications SET end_date = date + (6 - EXTRACT(DOW FROM date)::int)
WHERE end_date IS NULL AND period = 'week';

-- 'month': last day of the calendar month containing `date`.
UPDATE dedications SET end_date = (date_trunc('month', date) + interval '1 month - 1 day')::date
WHERE end_date IS NULL AND period = 'month';

-- ── 3. Make it required going forward ───────────────────────────────────────
-- Every existing row now has a value from the backfill above; new rows must set it
-- explicitly (the admin form defaults it to `date` for a same-day dedication).
ALTER TABLE dedications ALTER COLUMN end_date SET NOT NULL;
ALTER TABLE dedications ADD CONSTRAINT dedications_end_date_after_date CHECK (end_date >= date);

-- Index for the new range query (`date <= today AND end_date >= today`).
CREATE INDEX IF NOT EXISTS dedications_end_date_idx ON dedications (end_date);

-- No RLS policy changes needed — existing policies key off `status`, not date columns.
