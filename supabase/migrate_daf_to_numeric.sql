-- Migration: change daf column from int to numeric(4,1)
-- This allows half-daf values (e.g. 5.5 = between daf 5a and daf 6a)
-- Run once in the Supabase SQL editor (Database → SQL Editor → New query)

ALTER TABLE episode_audio ALTER COLUMN daf TYPE numeric(4,1);
