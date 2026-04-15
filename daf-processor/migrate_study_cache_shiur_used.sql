-- Migration: add shiur_used column to study_cache.
-- Run once in the Supabase SQL editor.
--
-- shiur_used = true  → summary was generated with the lecture rewrite as context.
-- shiur_used = false → summary was generated from Sefaria text only (legacy rows).
--
-- Existing rows default to false so the app will regenerate them the next time
-- the user views a section for a daf that has shiur data available.

alter table study_cache
  add column if not exists shiur_used boolean not null default false;
