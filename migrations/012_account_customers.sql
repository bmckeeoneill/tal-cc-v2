-- Similar customers lock/dismiss
CREATE TABLE IF NOT EXISTS account_customers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid REFERENCES accounts(id) ON DELETE CASCADE,
  customer_id uuid REFERENCES customers(id) ON DELETE CASCADE,
  rep_id text,
  status text NOT NULL CHECK (status IN ('locked', 'dismissed')),
  created_at timestamptz DEFAULT now(),
  UNIQUE(account_id, customer_id)
);

-- Priority star on accounts
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS starred boolean DEFAULT false;

-- Outreach prompt template per rep
CREATE TABLE IF NOT EXISTS outreach_config (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rep_id text NOT NULL UNIQUE,
  prompt_template text NOT NULL,
  updated_at timestamptz DEFAULT now()
);
