-- Migration 002
-- Add unique constraints required for CSV upsert logic.

ALTER TABLE accounts
    ADD CONSTRAINT uq_accounts_zi_id_rep_id
    UNIQUE (zi_id, rep_id);

ALTER TABLE accounts
    ADD CONSTRAINT uq_accounts_name_rep_id
    UNIQUE (company_name, rep_id);
