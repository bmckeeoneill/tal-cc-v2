-- Phase 5: Extend events table + create account_events

-- Add Phase 5 columns to existing events table
ALTER TABLE events ADD COLUMN IF NOT EXISTS event_name      text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS event_type      text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS region          text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS registration_url text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS seismic_url     text;
ALTER TABLE events ADD COLUMN IF NOT EXISTS raw_email_id    uuid REFERENCES signals_raw(id);

-- Unique index for dedup on insert
CREATE UNIQUE INDEX IF NOT EXISTS events_name_date_idx ON events (event_name, event_date)
    WHERE event_name IS NOT NULL;

-- Account-event junction table
CREATE TABLE IF NOT EXISTS account_events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    event_id        uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    match_reason    text NOT NULL,
    created_at      timestamptz DEFAULT now(),
    UNIQUE (account_id, event_id)
);
