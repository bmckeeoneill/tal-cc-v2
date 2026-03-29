-- TAL Command Center — Migration 004
-- Add file_url to signals_raw for Storage links.
-- Add source and file_url to signals_processed for extraction path tracking.

ALTER TABLE signals_raw
  ADD COLUMN IF NOT EXISTS file_url text;

ALTER TABLE signals_processed
  ADD COLUMN IF NOT EXISTS source  text,
  ADD COLUMN IF NOT EXISTS file_url text;
