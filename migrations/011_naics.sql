ALTER TABLE accounts
  ADD COLUMN IF NOT EXISTS naics_code text,
  ADD COLUMN IF NOT EXISTS naics_description text,
  ADD COLUMN IF NOT EXISTS naics_confidence text,
  ADD COLUMN IF NOT EXISTS naics_notes text;
