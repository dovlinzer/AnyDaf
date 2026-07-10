-- AnyDaf Dedications — Database Setup
-- Run this in Supabase SQL Editor (Dashboard → SQL Editor → New query)
-- Safe to run on a fresh table or one already created by the initial setup.

-- ── 1. Schema changes ──────────────────────────────────────────────────────

-- Add status column (public submissions = 'pending', admin-created = 'approved')
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'pending';

-- Add period column ('today' | 'week' | 'month')
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS period text NOT NULL DEFAULT 'today';

-- Add preposition column ('in memory of' | 'in honor of' | 'on the occasion of' | '')
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS preposition text NOT NULL DEFAULT '';

-- Contact fields (admin use, not shown in app)
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS dedicator_email text,
  ADD COLUMN IF NOT EXISTS dedicator_phone text,
  ADD COLUMN IF NOT EXISTS dedicatee_email text,
  ADD COLUMN IF NOT EXISTS dedicatee_phone text;

-- Optional photo URL (Supabase Storage public link)
ALTER TABLE dedications
  ADD COLUMN IF NOT EXISTS photo_url text;

-- Allow honoree_name and occasion to be empty strings
ALTER TABLE dedications
  ALTER COLUMN honoree_name SET DEFAULT '',
  ALTER COLUMN occasion SET DEFAULT '';

-- Remove the date UNIQUE constraint — you may now have e.g. a 'today' entry
-- and a 'month' entry whose anchor date falls in the same month.
ALTER TABLE dedications DROP CONSTRAINT IF EXISTS dedications_date_key;

-- Index for fast status filtering
CREATE INDEX IF NOT EXISTS dedications_status_idx ON dedications (status);
CREATE INDEX IF NOT EXISTS dedications_date_idx   ON dedications (date);

-- ── 2. RLS policies ────────────────────────────────────────────────────────

ALTER TABLE dedications ENABLE ROW LEVEL SECURITY;

-- Drop any previously created policies before recreating them
DROP POLICY IF EXISTS "public read"            ON dedications;
DROP POLICY IF EXISTS "approved read"          ON dedications;
DROP POLICY IF EXISTS "public insert pending"  ON dedications;
DROP POLICY IF EXISTS "admin all"              ON dedications;
DROP POLICY IF EXISTS "anon read approved"     ON dedications;
DROP POLICY IF EXISTS "authenticated read all" ON dedications;
DROP POLICY IF EXISTS "anon insert pending"    ON dedications;
DROP POLICY IF EXISTS "authenticated insert"   ON dedications;
DROP POLICY IF EXISTS "authenticated update"   ON dedications;
DROP POLICY IF EXISTS "authenticated delete"   ON dedications;

-- App (anon key) can only read approved entries
CREATE POLICY "anon read approved" ON dedications
  FOR SELECT TO anon
  USING (status = 'approved');

-- Logged-in admin can read everything
CREATE POLICY "authenticated read all" ON dedications
  FOR SELECT TO authenticated
  USING (true);

-- Anyone can submit a pending dedication (anon users can only insert 'pending')
CREATE POLICY "anon insert pending" ON dedications
  FOR INSERT TO anon
  WITH CHECK (status = 'pending');

-- Admin can insert with any status (including 'approved')
CREATE POLICY "authenticated insert" ON dedications
  FOR INSERT TO authenticated
  WITH CHECK (true);

-- Admin can update any row
CREATE POLICY "authenticated update" ON dedications
  FOR UPDATE TO authenticated
  USING (true) WITH CHECK (true);

-- Admin can delete any row
CREATE POLICY "authenticated delete" ON dedications
  FOR DELETE TO authenticated
  USING (true);

-- ── 3. Supabase Storage bucket for dedication photos ──────────────────────
-- Creates a public bucket called 'dedication-photos'.
-- Safe to run more than once (ON CONFLICT DO NOTHING).
INSERT INTO storage.buckets (id, name, public)
  VALUES ('dedication-photos', 'dedication-photos', true)
  ON CONFLICT (id) DO NOTHING;

-- Drop existing storage policies before recreating them
DROP POLICY IF EXISTS "public upload dedication photos"  ON storage.objects;
DROP POLICY IF EXISTS "public read dedication photos"   ON storage.objects;
DROP POLICY IF EXISTS "authenticated manage dedication photos" ON storage.objects;

-- Anyone (anon) can upload a photo (public submission)
CREATE POLICY "public upload dedication photos" ON storage.objects
  FOR INSERT TO anon
  WITH CHECK (bucket_id = 'dedication-photos');

-- Anyone can read / view dedication photos
CREATE POLICY "public read dedication photos" ON storage.objects
  FOR SELECT TO anon
  USING (bucket_id = 'dedication-photos');

-- Admin can update or delete photos
CREATE POLICY "authenticated manage dedication photos" ON storage.objects
  FOR ALL TO authenticated
  USING (bucket_id = 'dedication-photos')
  WITH CHECK (bucket_id = 'dedication-photos');

-- ── 4. Admin user ──────────────────────────────────────────────────────────
-- Go to: Supabase Dashboard → Authentication → Users → Add user
-- Email:    dlinzer@yctorah.org
-- Password: (choose a strong password)
-- Then use those credentials in the Admin Login section of dedication-form.html
