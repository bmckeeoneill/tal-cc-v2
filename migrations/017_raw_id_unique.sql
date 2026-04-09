-- Prevent duplicate processed signals and review queue entries for the same raw email.
-- Required for upsert on_conflict="raw_id" in insert_signals_processed / insert_review_queue.

ALTER TABLE signals_processed
    ADD CONSTRAINT uq_signals_processed_raw_id UNIQUE (raw_id);

ALTER TABLE signal_review_queue
    ADD CONSTRAINT uq_review_queue_raw_id UNIQUE (raw_id);
