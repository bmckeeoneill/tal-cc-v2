-- Add confirmed flag to events table
-- Existing events are confirmed by default; AI-parsed events start unconfirmed
ALTER TABLE events ADD COLUMN IF NOT EXISTS confirmed boolean NOT NULL DEFAULT true;
