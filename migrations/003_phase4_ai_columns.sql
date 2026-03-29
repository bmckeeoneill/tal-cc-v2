-- TAL Command Center — Migration 003
-- Phase 4: add columns needed for AI processing pipeline.

-- signals_processed: track model version and processing timestamp
ALTER TABLE signals_processed
  ADD COLUMN IF NOT EXISTS model_version text,
  ADD COLUMN IF NOT EXISTS processed_at  timestamptz;

-- signal_review_queue: store Claude-extracted name and best fuzzy candidate
ALTER TABLE signal_review_queue
  ADD COLUMN IF NOT EXISTS extracted_name  text,
  ADD COLUMN IF NOT EXISTS best_match_name text;

-- weekly_analysis: store trend direction
ALTER TABLE weekly_analysis
  ADD COLUMN IF NOT EXISTS trend text;

-- ai_query_log: link log entries back to a raw signal and label the call type
ALTER TABLE ai_query_log
  ADD COLUMN IF NOT EXISTS signal_id uuid REFERENCES signals_raw(id),
  ADD COLUMN IF NOT EXISTS call_type text;

-- outreach_templates: AI-generated outreach suggestions per signal
CREATE TABLE IF NOT EXISTS outreach_templates (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rep_id        text,
    account_id    uuid REFERENCES accounts(id),
    signal_id     uuid REFERENCES signals_raw(id),
    trigger_type  text,
    email_body    text,
    model_version text,
    generated_at  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outreach_account ON outreach_templates(account_id);
CREATE INDEX IF NOT EXISTS idx_outreach_signal  ON outreach_templates(signal_id);
