-- Phase 6: Tech stack, SDR, Leads, Event Invites, Briefing flags

-- accounts: tech stack and SDR fields
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS tech_stack      text[];
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS sdr_name        text;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS sdr_assigned_at timestamptz;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS briefing_sent_at timestamptz;

-- account_events: flag for briefing
ALTER TABLE account_events ADD COLUMN IF NOT EXISTS flagged_for_briefing boolean DEFAULT false;

-- leads table
CREATE TABLE IF NOT EXISTS leads (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name   text,
    website        text,
    file_url       text,
    raw_email_id   uuid REFERENCES signals_raw(id),
    status         text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'dismissed')),
    created_at     timestamptz DEFAULT now()
);

-- event_invites table
CREATE TABLE IF NOT EXISTS event_invites (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id     uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    event_id       uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    invite_body    text,
    model_version  text,
    generated_at   timestamptz DEFAULT now(),
    UNIQUE (account_id, event_id)
);
