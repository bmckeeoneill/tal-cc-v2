-- TAL Command Center — Migration 001
-- Initial schema. Run once against Supabase.
-- All tables include rep_id for future multi-rep support.

-- ============================================================
-- accounts
-- Source of truth for TAL accounts. Loaded from CSV.
-- ============================================================
CREATE TABLE IF NOT EXISTS accounts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    zi_id           text,
    company_name    text NOT NULL,
    domain          text,
    phone           text,
    street          text,
    city            text,
    state           text,
    zip             text,
    country         text,
    industry        text,
    nscorp_url      text,
    linkedin_url    text,
    sales_rep       text,
    rep_id          text,
    score           integer NOT NULL DEFAULT 0,
    signal_count    integer NOT NULL DEFAULT 0,
    last_signal_date date,
    last_signal_type text,
    last_touched    date,
    next_action     text,
    revenue_range   text,
    employees       text,
    zi_validated    boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_accounts_rep_id   ON accounts(rep_id);
CREATE INDEX IF NOT EXISTS idx_accounts_industry ON accounts(industry);
CREATE INDEX IF NOT EXISTS idx_accounts_state    ON accounts(state);

-- ============================================================
-- signals_raw
-- Append-only Postmark ingest. Never modified after insert.
-- ============================================================
CREATE TABLE IF NOT EXISTS signals_raw (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id               text,
    received_at          timestamptz,
    from_email           text,
    subject              text,
    body_text            text,
    body_html            text,
    attachments          jsonb,
    postmark_message_id  text UNIQUE,
    processed            boolean NOT NULL DEFAULT false,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_raw_rep_id    ON signals_raw(rep_id);
CREATE INDEX IF NOT EXISTS idx_signals_raw_processed ON signals_raw(processed);

-- ============================================================
-- signals_processed
-- Extracted, tagged, AI-summarized signals.
-- account_id null = unmatched; raw_id null = Pipeline Scout source.
-- ============================================================
CREATE TABLE IF NOT EXISTS signals_processed (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_id           uuid REFERENCES signals_raw(id),
    account_id       uuid REFERENCES accounts(id),
    rep_id           text,
    signal_type      text,
    signal_source    text,
    source_url       text,
    headline         text,
    summary          text,
    signal_date      date,
    signal_score     integer,
    global_event     boolean NOT NULL DEFAULT false,
    match_confidence numeric(4,2),
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_signals_proc_account ON signals_processed(account_id);
CREATE INDEX IF NOT EXISTS idx_signals_proc_rep     ON signals_processed(rep_id);
CREATE INDEX IF NOT EXISTS idx_signals_proc_date    ON signals_processed(signal_date DESC);
CREATE INDEX IF NOT EXISTS idx_signals_proc_type    ON signals_processed(signal_type);

-- ============================================================
-- signal_review_queue
-- Low-confidence and unmatched signals. Feeds Unmatched Signals tile.
-- ============================================================
CREATE TABLE IF NOT EXISTS signal_review_queue (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_id                  uuid REFERENCES signals_raw(id),
    rep_id                  text,
    content_type            text,
    ai_summary              text,
    storage_url             text,
    reason                  text,
    match_confidence        numeric(4,2),
    suggested_account_id    uuid REFERENCES accounts(id),
    resolved_to_account_id  uuid REFERENCES accounts(id),
    reviewed                boolean NOT NULL DEFAULT false,
    reviewed_at             timestamptz,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_review_queue_rep      ON signal_review_queue(rep_id);
CREATE INDEX IF NOT EXISTS idx_review_queue_reviewed ON signal_review_queue(reviewed);

-- ============================================================
-- events
-- Marketing calendar.
-- ============================================================
CREATE TABLE IF NOT EXISTS events (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id        text,
    name          text NOT NULL,
    event_date    date,
    location      text,
    virtual       boolean NOT NULL DEFAULT false,
    description   text,
    account_count integer NOT NULL DEFAULT 0,
    status        text,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS event_accounts (
    event_id   uuid REFERENCES events(id)   ON DELETE CASCADE,
    account_id uuid REFERENCES accounts(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, account_id)
);

-- ============================================================
-- tal_changes
-- History of accounts added/removed from the TAL.
-- ============================================================
CREATE TABLE IF NOT EXISTS tal_changes (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id       text,
    company_name text,
    account_id   uuid REFERENCES accounts(id),
    industry     text,
    state        text,
    change_type  text,
    change_date  date,
    note         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tal_changes_rep  ON tal_changes(rep_id);
CREATE INDEX IF NOT EXISTS idx_tal_changes_date ON tal_changes(change_date DESC);

-- ============================================================
-- activity_log
-- Append-only feed for the Recent Activity tile.
-- ============================================================
CREATE TABLE IF NOT EXISTS activity_log (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id         text,
    account_id     uuid REFERENCES accounts(id),
    account_name   text,
    industry       text,
    state          text,
    activity_type  text,
    activity_label text,
    detail         text,
    activity_date  date,
    created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_activity_rep  ON activity_log(rep_id);
CREATE INDEX IF NOT EXISTS idx_activity_date ON activity_log(activity_date DESC);

-- ============================================================
-- weekly_analysis
-- Per-account AI analysis. One row per account per week.
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_analysis (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id    uuid REFERENCES accounts(id),
    rep_id        text,
    week_of       date,
    summary       text,
    model_version text,
    generated_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (account_id, week_of)
);

-- ============================================================
-- content_library
-- NetSuite assets tagged by vertical and content type.
-- ============================================================
CREATE TABLE IF NOT EXISTS content_library (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    title        text NOT NULL,
    content_type text,
    vertical     text,
    description  text,
    url          text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS account_content (
    account_id uuid REFERENCES accounts(id)        ON DELETE CASCADE,
    content_id uuid REFERENCES content_library(id) ON DELETE CASCADE,
    PRIMARY KEY (account_id, content_id)
);

-- ============================================================
-- account_one_pagers
-- AI-generated one-pagers. All versions kept, never overwritten.
-- ============================================================
CREATE TABLE IF NOT EXISTS account_one_pagers (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id   uuid REFERENCES accounts(id),
    rep_id       text,
    version      integer NOT NULL DEFAULT 1,
    content      text,
    saved        boolean NOT NULL DEFAULT false,
    generated_at timestamptz,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_one_pagers_account ON account_one_pagers(account_id);

-- ============================================================
-- weekly_digest
-- Top accounts to contact each week with scoring.
-- ============================================================
CREATE TABLE IF NOT EXISTS weekly_digest (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id           text,
    week_of          date,
    account_id       uuid REFERENCES accounts(id),
    rank             integer,
    score            integer,
    top_signal_type  text,
    reason           text,
    suggested_action text,
    signal_count     integer,
    urgency          text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (rep_id, week_of, account_id)
);

CREATE INDEX IF NOT EXISTS idx_digest_rep_week ON weekly_digest(rep_id, week_of);

-- ============================================================
-- ai_query_log
-- Natural language query history (Phase 4).
-- ============================================================
CREATE TABLE IF NOT EXISTS ai_query_log (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id        text,
    question      text,
    prompt_used   text,
    model_version text,
    response      text,
    queried_at    timestamptz NOT NULL DEFAULT now()
);
