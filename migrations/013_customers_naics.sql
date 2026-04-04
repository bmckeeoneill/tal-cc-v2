ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS naics_code        text,
  ADD COLUMN IF NOT EXISTS naics_description text,
  ADD COLUMN IF NOT EXISTS sub_industry      text,
  ADD COLUMN IF NOT EXISTS what_they_do      text,
  ADD COLUMN IF NOT EXISTS business_model    text;
