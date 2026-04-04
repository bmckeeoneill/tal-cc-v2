-- Migration 008: contacts table
-- Stores contacts extracted from forwarded screenshot emails (subject: "contacts")

CREATE TABLE IF NOT EXISTS contacts (
    id          BIGSERIAL PRIMARY KEY,
    account_id  UUID REFERENCES accounts(id),
    rep_id      TEXT NOT NULL DEFAULT 'brianoneill',
    name        TEXT,
    title       TEXT,
    email       TEXT,
    phone       TEXT,
    linkedin_url TEXT,
    raw_email_id UUID,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_contacts_account_id ON contacts(account_id);
CREATE INDEX IF NOT EXISTS idx_contacts_rep_id     ON contacts(rep_id);
