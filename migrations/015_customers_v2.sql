-- Add enriched columns to customers table for 6k reference customer load
ALTER TABLE customers ADD COLUMN IF NOT EXISTS v_rank integer;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS references_descriptors text;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS highlights text;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS business_type text;
ALTER TABLE customers ADD COLUMN IF NOT EXISTS company_size text;

-- Unique constraint on website for upsert
ALTER TABLE customers ADD CONSTRAINT customers_website_unique UNIQUE (website);

-- IVFFlat index for pgvector similarity search
CREATE INDEX IF NOT EXISTS customers_embedding_idx
    ON customers USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
