-- Similar Customers feature
-- Requires pgvector extension. Run this in Supabase SQL editor.

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Customers table
create table if not exists customers (
    id               uuid primary key default gen_random_uuid(),
    company_name     text not null,
    website          text,
    industry         text,
    revenue_range    text,
    state            text,
    reference_status text,
    notes            text,
    embedding        vector(1536),
    created_at       timestamptz default now()
);

-- 3. IVFFlat index for fast cosine similarity search
create index if not exists customers_embedding_idx
    on customers using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

-- 4. RPC function for similarity search
create or replace function match_customers(
    query_embedding vector(1536),
    match_count     int
)
returns table (
    id               uuid,
    company_name     text,
    website          text,
    industry         text,
    revenue_range    text,
    state            text,
    reference_status text,
    notes            text,
    similarity       float
)
language sql stable
as $$
    select
        id,
        company_name,
        website,
        industry,
        revenue_range,
        state,
        reference_status,
        notes,
        1 - (embedding <=> query_embedding) as similarity
    from customers
    order by embedding <=> query_embedding
    limit match_count;
$$;
